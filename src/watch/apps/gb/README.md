# gb: the Game Boy core

`peanut_gb.h` is [Peanut-GB](https://github.com/deltabeard/Peanut-GB) by Mahyar Koshkouei (MIT License, the notice is at the top of the file; parts from SameBoy by Lior Halphon,
also MIT), unchanged, from commit `d0bcca771c83a2638c93a9ae61f3d51f226dc905`. The watch app that uses it is [`../gameboy.c`](../gameboy.c); it provides `memset`, `memcpy` and
`abort`, builds it without sound, and keeps all its state in the app heap (the `.f3x` rules: no globals, no libc).

No ROM is in this repository. Use only games you have the right to use: homebrew, or dumps of your own cartridges.
