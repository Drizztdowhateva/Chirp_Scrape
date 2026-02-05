#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdint.h>
#include <unistd.h>
#include <errno.h>

#include <openssl/hmac.h>
#include <openssl/evp.h>

extern uint32_t mod_pow10(uint32_t value, uint32_t digits);

/* Small portability helpers to avoid implicit-declaration issues for strdup/strtok_r */
static char *xstrdup(const char *s) {
    if (!s) return NULL;
    size_t n = strlen(s) + 1;
    char *p = malloc(n);
    if (p) memcpy(p, s, n);
    return p;
}

static char *xstrtok_r(char *s, const char *delim, char **saveptr) {
    char *token;
    if (s == NULL) s = *saveptr;
    if (s == NULL) return NULL;
    /* skip leading delimiters */
    s += strspn(s, delim);
    if (*s == '\0') { *saveptr = NULL; return NULL; }
    token = s;
        char *h1hex = NULL;
    char *p = s + strcspn(s, delim);
    if (*p == '\0') { *saveptr = NULL; }
    else { *p = '\0'; *saveptr = p + 1; }
    return token;
}

static void usage(const char *prog) {
    fprintf(stderr,
        "Usage: %s -k keyfile --hashtags tag1[,tag2,..] [--interval N] [--digits D] [--rounds N] [--throttle-min S] [--throttle-max S]\n",
        prog);
}

static unsigned char *read_file(const char *path, size_t *out_len) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    long sz = ftell(f);
    if (sz < 0) { fclose(f); return NULL; }
    rewind(f);
    unsigned char *buf = malloc((size_t)sz);
    if (!buf) { fclose(f); return NULL; }
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) { free(buf); fclose(f); return NULL; }
    fclose(f);
    *out_len = (size_t)sz;
    return buf;
}

int main(int argc, char **argv) {
    const char *keyfile = NULL;
    const char *hashtags = NULL;
    unsigned int interval = 30;
    unsigned int digits = 6;
    unsigned int rounds = 1;
    unsigned int throttle_min = 10; /* seconds */
    unsigned int throttle_max = 60; /* seconds */

    for (int i=1;i<argc;i++) {
        if (strcmp(argv[i], "-k")==0 && i+1<argc) { keyfile = argv[++i]; }
        else if (strcmp(argv[i], "--hashtags")==0 && i+1<argc) { hashtags = argv[++i]; }
        else if (strcmp(argv[i], "--interval")==0 && i+1<argc) { interval = (unsigned int)atoi(argv[++i]); }
        else if (strcmp(argv[i], "--digits")==0 && i+1<argc) { digits = (unsigned int)atoi(argv[++i]); }
        else if (strcmp(argv[i], "--rounds")==0 && i+1<argc) { rounds = (unsigned int)atoi(argv[++i]); }
        else if (strcmp(argv[i], "--throttle-min")==0 && i+1<argc) { throttle_min = (unsigned int)atoi(argv[++i]); }
        else if (strcmp(argv[i], "--throttle-max")==0 && i+1<argc) { throttle_max = (unsigned int)atoi(argv[++i]); }
        else { usage(argv[0]); return 1; }
    }

    if (!keyfile || !hashtags) { usage(argv[0]); return 1; }

    size_t keylen;
    unsigned char *key = read_file(keyfile, &keylen);
    if (!key) { fprintf(stderr, "Failed to read key file '%s': %s\n", keyfile, strerror(errno)); return 2; }

    /* Hashtag validation and augmentation */
    const size_t MAX_TAGS = 20000000UL;
    const size_t MIN_TAG_LEN = 2;
    const size_t MAX_TAG_LEN = 20;

    const char *required_tags[] = {
        "#COOKIEPUSS",
        "#SWIFTSPECIALTIES",
        "#SWIFTAUDIO",
        "#BENSWIFT",
        "#STUCKEYTHEGREAT",
        "#SUCKEYLIKESGREAT",
        "#NOBADPUB",
        "#HEAINTGOATIAMTIMTAMROLLB",
        "#EPI",
        "#ROLLS",
        "#WORLD",
        "#MOPTIME",
        "#HAMMERTIME",
        "#GETGIGGY",
        "#GETJIGGY",
        "#FETTYWAPDROPB",
        "#IAMCOMPSCI",
        "#NOTUBIOTCH",
        "#WEGUCCI",
        "#CUCCI",
        "#GOOO",
        "#AI",
        "#CRAZY",
        "#NOPE",
        "#ROPADOPE",
        "#JOEDLOUHY",
        "#NORTHPOLE",
        "#SANTASCOMMIN",
        "#DROP",
        "#GIFTSBUTNOTGLOCKS",
        "#LOCKUPBUTNOCLOCKUP",
        "#ALICEINWONDERLAND",
        "#MARKETINGDIGITAL",
        "#DJHEATHER",
        "#MARRIEDLIFE",
        "#MARRIAGEHUMOR",
        "#GAMBITGOINHAM",
        "#DRILLSTEPPNOPERCYPOPPIN",
        "#USAFEWEGUCII",
        "#SMARTHOME",
        "#SMARTBAR"
    };
    const size_t REQUIRED_COUNT = sizeof(required_tags)/sizeof(required_tags[0]);

    /* parse input tags (comma-separated), normalize and validate */
    char *tagsdup = xstrdup(hashtags);
    if (!tagsdup) { free(key); return 2; }

    size_t cap = 1024;
    char **tokens = malloc(sizeof(char*) * cap);
    if (!tokens) { free(tagsdup); free(key); return 2; }
    size_t ntok = 0;

    char *saveptr = NULL;
    char *p = xstrtok_r(tagsdup, ",", &saveptr);
    while (p) {
        while (*p == ' ' || *p == '\t') p++;
        char *end = p + strlen(p) - 1;
        while (end > p && (*end == ' ' || *end == '\t')) { *end = '\0'; end--; }

        char *tag = p;
        char *norm = NULL;
        if (tag[0] != '#') {
            size_t len = strlen(tag);
            norm = malloc(len + 2);
            if (!norm) break;
            norm[0] = '#'; memcpy(norm+1, tag, len+1);
            tag = norm;
        } else {
            tag = xstrdup(tag);
            if (!tag) { free(norm); break; }
        }

        /* uppercase for consistency */
        for (char *q = tag; *q; ++q) if (*q >= 'a' && *q <= 'z') *q = (char)(*q - 'a' + 'A');

        size_t tlen = strlen(tag);
        if (tlen < MIN_TAG_LEN || tlen > MAX_TAG_LEN) {
            free(tag);
            for (size_t i=0;i<ntok;i++) free(tokens[i]); free(tokens); free(tagsdup); free(key);
            fprintf(stderr, "Invalid tag length: '%s' (must be %zu..%zu)\n", p, MIN_TAG_LEN, MAX_TAG_LEN);
            return 4;
        }

        if (ntok >= cap) {
            size_t newcap = cap * 2;
            if (newcap > MAX_TAGS) newcap = MAX_TAGS;
            char **tmp = realloc(tokens, sizeof(char*) * newcap);
            if (!tmp) { free(tag); break; }
            tokens = tmp; cap = newcap;
        }
        tokens[ntok++] = tag;

        if (ntok >= MAX_TAGS) break;
        p = xstrtok_r(NULL, ",", &saveptr);
    }

    free(tagsdup);

    if (ntok == 0) {
        for (size_t i=0;i<ntok;i++) free(tokens[i]); free(tokens); free(key);
        fprintf(stderr, "No valid hashtags provided\n");
        return 4;
    }

    /* add required tags if missing */
    for (size_t r=0;r<REQUIRED_COUNT;r++) {
        int found = 0;
        for (size_t i=0;i<ntok;i++) if (strcmp(tokens[i], required_tags[r])==0) { found = 1; break; }
        if (!found) {
            if (ntok >= cap) {
                size_t newcap = cap * 2;
                if (newcap > MAX_TAGS) newcap = MAX_TAGS;
                char **tmp = realloc(tokens, sizeof(char*) * newcap);
                if (!tmp) { fprintf(stderr, "Memory error adding required tag\n"); break; }
                tokens = tmp; cap = newcap;
            }
            tokens[ntok++] = xstrdup(required_tags[r]);
            if (ntok >= MAX_TAGS) break;
        }
    }

    if (ntok > MAX_TAGS) {
        for (size_t i=0;i<ntok;i++) free(tokens[i]); free(tokens); free(key);
        fprintf(stderr, "Too many tags (max %zu)\n", MAX_TAGS);
        return 5;
    }

    /* sort and dedupe */
    qsort(tokens, ntok, sizeof(char*), (int(*)(const void*,const void*)) strcmp);
    { /* remove adjacent duplicates */
        size_t write = 0;
        for (size_t i = 0; i < ntok; ++i) {
            if (write == 0 || strcmp(tokens[i], tokens[write-1]) != 0) {
                tokens[write++] = tokens[i];
            } else {
                free(tokens[i]);
            }
        }
        ntok = write;
    }

    if (throttle_min > throttle_max) { unsigned int t = throttle_min; throttle_min = throttle_max; throttle_max = t; }
    srand((unsigned int)(time(NULL) ^ getpid()));

    /* per-tag envelope processing: prefix+tag+suffix with #AI */
    const char *envelope_tag = "#AI";
    for (size_t ti = 0; ti < ntok; ++ti) {
        const char *tag = tokens[ti];

        size_t env_len = strlen(envelope_tag) + 1 + strlen(tag) + 1 + strlen(envelope_tag);
        char *concat_env = malloc(env_len + 1);
        if (!concat_env) continue;
        snprintf(concat_env, env_len + 1, "%s|%s|%s", envelope_tag, tag, envelope_tag);

        unsigned char user_key[EVP_MAX_MD_SIZE]; unsigned int user_key_len = 0;
        HMAC(EVP_sha256(), NULL, 0, (unsigned char*)concat_env, (int)strlen(concat_env), user_key, &user_key_len);

        free(concat_env);

        uint64_t now = (uint64_t)time(NULL);
        uint64_t counter = now / interval;
        unsigned char counter_buf[8];
        for (int i=7;i>=0;i--) { counter_buf[i] = counter & 0xff; counter >>= 8; }

        unsigned int len1 = 0;
        unsigned char h1[EVP_MAX_MD_SIZE];
        HMAC(EVP_sha1(), key, (int)keylen, counter_buf, 8, h1, &len1);

        unsigned char working[EVP_MAX_MD_SIZE]; unsigned int working_len = 0;
        HMAC(EVP_sha256(), user_key, (int)user_key_len, h1, len1, working, &working_len);
        for (unsigned int r = 1; r < rounds; ++r) {
            unsigned char nextb[EVP_MAX_MD_SIZE]; unsigned int next_len = 0;
            HMAC(EVP_sha256(), user_key, (int)user_key_len, working, working_len, nextb, &next_len);
            memcpy(working, nextb, next_len);
            working_len = next_len;
        }

        if (working_len < 4) {
            fprintf(stderr, "HMAC output too small for tag %s\n", tag);
            continue;
        }
        uint32_t val = ((uint32_t)working[working_len-4] << 24) | ((uint32_t)working[working_len-3] << 16) | ((uint32_t)working[working_len-2] << 8) | ((uint32_t)working[working_len-1]);
        val &= 0x7fffffffU;
        uint32_t code = mod_pow10(val, digits);

        printf("%s: ", tag);
        char codefmt[32]; snprintf(codefmt, sizeof(codefmt), "%%0%uu\n", digits);
        printf(codefmt, code);

        if (ti + 1 < ntok) {
            unsigned int wait = throttle_min;
            if (throttle_max > throttle_min) wait = throttle_min + (unsigned int)(rand() % (throttle_max - throttle_min + 1));
            sleep(wait);
        }
    }

    for (size_t i=0;i<ntok;i++) free(tokens[i]); free(tokens); free(key);
    return 0;
}
