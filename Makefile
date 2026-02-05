CC = cc
CFLAGS = -O2 -Wall -std=c11
LDFLAGS = -lcrypto

all: rolling_code

rolling_code: rolling_code.c modpow10.c
	$(CC) $(CFLAGS) rolling_code.c modpow10.c -o rolling_code $(LDFLAGS)

clean:
	rm -f rolling_code key.secret
