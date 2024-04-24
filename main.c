#define _GNU_SOURCE
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <string.h>
#include <dirent.h>
#include <glob.h>
#include <libgen.h>
#include <time.h>
#include <stdarg.h>

void log_message(const char* message, ...) {
    time_t rawtime;
    char buf[10];
    time(&rawtime);
    struct tm* timeinfo = localtime(&rawtime);
    strftime(buf, 10, "%M:%S.000", timeinfo);

    char* rendered_message;
    va_list args;
    va_start(args, message);
    vasprintf(&rendered_message, message, args);
    va_end(args);

    fprintf(stderr, "%-9s - %-8s - %-8s - %s\n", buf, "INFO", "cloader", rendered_message);
}

char* path_join(const char* dir, const char* filename) {
    char* result = malloc(strlen(dir) + strlen(filename) + 2);
    if (!result) {
        perror("malloc failed");
        return NULL;
    }
    strcpy(result, dir);
    strcat(result, "/");
    strcat(result, filename);
    return result;
}

char* read_file(const char* path) {
    log_message("Reading %s", path);
    FILE* file = fopen(path, "rb");
    if (!file) {
        perror("fopen failed");
        return NULL;
    }
    fseek(file, 0, SEEK_END);
    long length = ftell(file);
    fseek(file, 0, SEEK_SET);
    char* buffer = malloc(length + 1);
    if (!buffer) {
        perror("malloc failed");
        fclose(file);
        return NULL;
    }
    fread(buffer, 1, length, file);
    fclose(file);
    buffer[length] = '\0';
    log_message("Read %ld bytes from %s", length, path);
    return buffer;
}

struct LsResult {
    char** files;
    size_t count;
};

struct LsResult ls(char* glob_pattern) {
    glob_t globbuf;
    char **files;
    if (0==glob(glob_pattern, 0, NULL, &globbuf)) {
        files = malloc((globbuf.gl_pathc + 1) * sizeof(char*));
        if (!files) {
            perror("malloc failed");
            globfree(&globbuf);
            return (struct LsResult) {NULL, 0};
        }
        for (size_t i = 0; i < globbuf.gl_pathc; i++) {
            files[i] = strdup(globbuf.gl_pathv[i]);
            if (!files[i]) {
                perror("strdup failed");
                for (size_t j = 0; j < i; j++) {
                    free(files[j]);
                }
                free(files);
                globfree(&globbuf);
                return (struct LsResult) {NULL, 0};
            }
        }
    } else {
        perror("glob failed");
        return (struct LsResult) {NULL, 0};
    }
    int count = globbuf.gl_pathc;
    globfree(&globbuf);
    log_message("Found %d files in %s", count, glob_pattern);
    return (struct LsResult) {files, count};
}

int file_to_fd(const char* path) {
    char* buffer = read_file(path);
    if (!buffer) {
        return -1;
    }
    int fd = syscall(SYS_memfd_create, basename((char*)path), 0);
    if (fd < 0) {
        perror("memfd_create failed");
        free(buffer);
        return -1;
    }
    write(fd, buffer, strlen(buffer));
    free(buffer);
    unlink(path);
    log_message("Moved %s to file descriptor %d", path, fd);
    return fd;
}

int main(int argc, char** argv) {
    char *root, *loader, *python;
    int loader_fd=-1;

    log_message("Starting cloader");

    root = getenv("POCKET_ASI_ROOT");
    if (!root) {
        perror("POCKET_ASI_ROOT not set");
        return 1;
    }
    loader = getenv("POCKET_ASI_LOADER");
    if (!loader) {
        perror("POCKET_ASI_LOADER not set");
        return 1;
    }
    python = getenv("POCKET_ASI_PYTHON");
    if (!python) {
        perror("POCKET_ASI_PYTHON not set");
        return 1;
    }

    log_message("Looking for loader %s in %s", loader, root);

    char* pattern = path_join(root, "*");
    struct LsResult ls_result = ls(pattern);
    char** file = ls_result.files;
    free(pattern);

    char** names = malloc(sizeof(char*) * ls_result.count);
    int* fds = malloc(sizeof(int) * ls_result.count);

    int json_bytes = 3;
    for (; *file; file++) {
        int fd = file_to_fd(*file);
        char* file_basename = strdup(basename(*file));
        names[file - ls_result.files] = file_basename;
        json_bytes += strlen(names[file - ls_result.files]) + 3;
        fds[file - ls_result.files] = fd;
        json_bytes += snprintf(NULL, 0, "%d", fd);
        if (file - ls_result.files < ls_result.count - 1) json_bytes++;

        if (strcmp(file_basename, loader) == 0) {
            log_message("Found loader %s in FD %d", loader, fd);
            loader_fd = fd;
        }
    }

    if (loader_fd == -1) {
        perror("Loader not found");
        return 1;
    }

    char* json = malloc(json_bytes);
    if (!json) {
        perror("malloc failed");
        return 1;
    }

    char* json_ptr = json;
    json_ptr += sprintf(json_ptr, "{");
    for (int i = 0; i < ls_result.count; i++) {
        json_ptr += sprintf(json_ptr, "\"%s\":%d", names[i], fds[i]);
        if (i < ls_result.count - 1) {
            json_ptr += sprintf(json_ptr, ",");
        }
    }
    json_ptr += sprintf(json_ptr, "}");

    for (int i = 0; i < ls_result.count; i++) {
        free(names[i]);
    }
    free(fds);
    free(names);

    if (setenv("POCKET_ASI_FILES", json, 1) != 0) {
        perror("setenv failed");
        return 1;
    }

    log_message("Exported FDs to environmment");
    free(json);

    char* loader_fd_file = malloc(14 + snprintf(NULL, 0, "%d", loader_fd));
    sprintf(loader_fd_file, "/proc/self/fd/%d", loader_fd);

    char* python_argv[] = {python, loader_fd_file, NULL};

    log_message("Executing %s %s", python, loader_fd_file);

    unlink(argv[0]);
    rmdir(root);

    log_message("Removed %s and %s", argv[0], root);

    execv(python, python_argv);

    return 0;
}
