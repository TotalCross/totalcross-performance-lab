#define _GNU_SOURCE
#include <errno.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
/*
 * Test-only interposition of glibc's _FORTIFY_SOURCE realpath check.
 * The master VM calls __realpath_chk with a 1024-byte buffer, which
 * fails when glibc PATH_MAX is larger. Keep the master VM unchanged.
 * This shim changes only path canonicalization, not image decoding,
 * PNG or zlib symbol binding.
 */
char *__realpath_chk(const char *path, char *output, size_t capacity) {
    char *resolved = realpath(path, NULL);
    size_t length;
    if (!resolved) return NULL;
    if (!output) return resolved;
    length = strlen(resolved) + 1;
    if (length > capacity) {
        free(resolved);
        errno = ENAMETOOLONG;
        return NULL;
    }
    memcpy(output, resolved, length);
    free(resolved);
    return output;
}
