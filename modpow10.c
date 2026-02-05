#include <stdint.h>

uint32_t mod_pow10(uint32_t value, uint32_t digits) {
    if (digits == 0) return 0;
    uint32_t pow = 1;
    for (uint32_t i = 0; i < digits; ++i) pow *= 10U;
    return value % pow;
}
