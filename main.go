package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io/fs"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

type Config struct {
	Port         int
	Dirs         []string
	FriendlyName string
}

type FileEntry struct {
	Path string `json:"path"`
	Name string `json:"name"`
	Size int64  `json:"size"`
}

type ListResponse struct {
	Host  string      `json:"host"`
	Files []FileEntry `json:"files"`
}

type dirFlag []string

func (d *dirFlag) String() string { return fmt.Sprintf("%v", *d) }
func (d *dirFlag) Set(value string) error {
	*d = append(*d, value)
	return nil
}

var config Config

func main() {
	var dirs dirFlag

	flag.IntVar(&config.Port, "port", 8080, "Port to listen on")
	flag.Var(&dirs, "dir", "Directory to scan (can be specified multiple times)")
	flag.StringVar(&config.FriendlyName, "friendlyname", "", "Friendly name for this host (defaults to hostname)")
	flag.Parse()

	config.Dirs = dirs

	if len(config.Dirs) == 0 {
		log.Fatal("At least one --dir must be specified")
	}

	if config.FriendlyName == "" {
		hostname, err := os.Hostname()
		if err != nil {
			config.FriendlyName = "unknown"
		} else {
			config.FriendlyName = hostname
		}
	}

	http.HandleFunc("/list", handleList)
	http.HandleFunc("/filter", handleFilter)
	http.HandleFunc("/health", handleHealth)

	addr := fmt.Sprintf(":%d", config.Port)
	log.Printf("Starting filesystem-lister on %s (host: %s)", addr, config.FriendlyName)
	log.Printf("Scanning directories: %v", config.Dirs)
	log.Fatal(http.ListenAndServe(addr, nil))
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok", "host": config.FriendlyName})
}

func handleList(w http.ResponseWriter, r *http.Request) {
	var files []FileEntry

	for _, dir := range config.Dirs {
		err := filepath.WalkDir(dir, func(path string, d fs.DirEntry, err error) error {
			if err != nil {
				log.Printf("Error accessing %s: %v", path, err)
				return nil
			}

			if d.IsDir() {
				return nil
			}

			info, err := d.Info()
			if err != nil {
				log.Printf("Error getting info for %s: %v", path, err)
				return nil
			}

			files = append(files, FileEntry{
				Path: path,
				Name: d.Name(),
				Size: info.Size(),
			})

			return nil
		})
		if err != nil {
			log.Printf("Error walking directory %s: %v", dir, err)
		}
	}

	response := ListResponse{
		Host:  config.FriendlyName,
		Files: files,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func handleFilter(w http.ResponseWriter, r *http.Request) {
	pattern := r.URL.Query().Get("q")
	if pattern == "" {
		http.Error(w, "missing 'q' parameter", http.StatusBadRequest)
		return
	}

	var files []FileEntry

	for _, dir := range config.Dirs {
		filepath.WalkDir(dir, func(path string, d fs.DirEntry, err error) error {
			if err != nil || d.IsDir() {
				return nil
			}

			if matchPattern(d.Name(), pattern) {
				info, _ := d.Info()
				size := int64(0)
				if info != nil {
					size = info.Size()
				}
				files = append(files, FileEntry{
					Path: path,
					Name: d.Name(),
					Size: size,
				})
			}
			return nil
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(ListResponse{Host: config.FriendlyName, Files: files})
}

// matchPattern does DOS-style wildcard matching (case-insensitive)
// *word* = contains, word* = prefix, *word = suffix, word = exact
func matchPattern(name, pattern string) bool {
	name = strings.ToLower(name)
	pattern = strings.ToLower(pattern)

	hasPrefix := strings.HasPrefix(pattern, "*")
	hasSuffix := strings.HasSuffix(pattern, "*")

	core := strings.Trim(pattern, "*")

	switch {
	case hasPrefix && hasSuffix:
		return strings.Contains(name, core)
	case hasPrefix:
		return strings.HasSuffix(name, core)
	case hasSuffix:
		return strings.HasPrefix(name, core)
	default:
		return name == pattern
	}
}
