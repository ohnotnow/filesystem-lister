package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestMatchPattern(t *testing.T) {
	tests := []struct {
		name    string
		pattern string
		want    bool
	}{
		// *word* = contains
		{"Movie.2024.1080p.mkv", "*movie*", true},
		{"Movie.2024.1080p.mkv", "*MOVIE*", true},
		{"Movie.2024.1080p.mkv", "*1080*", true},
		{"Movie.2024.1080p.mkv", "*notfound*", false},

		// word* = prefix
		{"Movie.2024.1080p.mkv", "movie*", true},
		{"Movie.2024.1080p.mkv", "MOVIE*", true},
		{"Movie.2024.1080p.mkv", "2024*", false},

		// *word = suffix
		{"Movie.2024.1080p.mkv", "*.mkv", true},
		{"Movie.2024.1080p.mkv", "*.MKV", true},
		{"Movie.2024.1080p.mkv", "*.avi", false},

		// exact match
		{"Movie.mkv", "movie.mkv", true},
		{"Movie.mkv", "MOVIE.MKV", true},
		{"Movie.mkv", "other.mkv", false},
	}

	for _, tt := range tests {
		t.Run(tt.name+"_"+tt.pattern, func(t *testing.T) {
			got := matchPattern(tt.name, tt.pattern)
			if got != tt.want {
				t.Errorf("matchPattern(%q, %q) = %v, want %v", tt.name, tt.pattern, got, tt.want)
			}
		})
	}
}

func TestHandleHealth(t *testing.T) {
	config.FriendlyName = "test-host"

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	w := httptest.NewRecorder()

	handleHealth(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp map[string]string
	json.Unmarshal(w.Body.Bytes(), &resp)

	if resp["status"] != "ok" {
		t.Errorf("expected status ok, got %s", resp["status"])
	}
	if resp["host"] != "test-host" {
		t.Errorf("expected host test-host, got %s", resp["host"])
	}
}

func TestHandleList(t *testing.T) {
	// Create a temp directory with test files
	tmpDir := t.TempDir()
	os.WriteFile(filepath.Join(tmpDir, "movie1.mkv"), []byte("test"), 0644)
	os.WriteFile(filepath.Join(tmpDir, "movie2.avi"), []byte("test2"), 0644)
	os.MkdirAll(filepath.Join(tmpDir, "subdir"), 0755)
	os.WriteFile(filepath.Join(tmpDir, "subdir", "movie3.mp4"), []byte("test3"), 0644)

	config.FriendlyName = "test-host"
	config.Dirs = []string{tmpDir}

	req := httptest.NewRequest(http.MethodGet, "/list", nil)
	w := httptest.NewRecorder()

	handleList(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	var resp ListResponse
	json.Unmarshal(w.Body.Bytes(), &resp)

	if resp.Host != "test-host" {
		t.Errorf("expected host test-host, got %s", resp.Host)
	}
	if len(resp.Files) != 3 {
		t.Errorf("expected 3 files, got %d", len(resp.Files))
	}
}

func TestHandleFilter(t *testing.T) {
	tmpDir := t.TempDir()
	os.WriteFile(filepath.Join(tmpDir, "Edge.of.Darkness.2010.1080p.mkv"), []byte("test"), 0644)
	os.WriteFile(filepath.Join(tmpDir, "Other.Movie.720p.mkv"), []byte("test2"), 0644)

	config.FriendlyName = "test-host"
	config.Dirs = []string{tmpDir}

	tests := []struct {
		query     string
		wantCount int
		wantCode  int
	}{
		{"*edge*", 1, http.StatusOK},
		{"*darkness*", 1, http.StatusOK},
		{"*.mkv", 2, http.StatusOK},
		{"*1080*", 1, http.StatusOK},
		{"*notfound*", 0, http.StatusOK},
		{"", 0, http.StatusBadRequest},
	}

	for _, tt := range tests {
		t.Run(tt.query, func(t *testing.T) {
			url := "/filter?q=" + tt.query
			if tt.query == "" {
				url = "/filter"
			}
			req := httptest.NewRequest(http.MethodGet, url, nil)
			w := httptest.NewRecorder()

			handleFilter(w, req)

			if w.Code != tt.wantCode {
				t.Errorf("expected status %d, got %d", tt.wantCode, w.Code)
			}

			if tt.wantCode == http.StatusOK {
				var resp ListResponse
				json.Unmarshal(w.Body.Bytes(), &resp)
				if len(resp.Files) != tt.wantCount {
					t.Errorf("expected %d files, got %d", tt.wantCount, len(resp.Files))
				}
			}
		})
	}
}
