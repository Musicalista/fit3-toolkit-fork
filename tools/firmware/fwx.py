"""fwx.py: list or extract the components of a Fit3 FWD firmware package (read-only).
    python3 -I fwx.py <package.bin> list
    python3 -I fwx.py <package.bin> main <out>        the main image (best1502x_b319_user.bin); code is linked at 0x2c080000 + file offset
    python3 -I fwx.py <package.bin> get <path> <out>  any component by its path on the watch"""
import io, struct, sys, zipfile

MAIN = "/user/ota/app/best1502x_b319_user.bin"
u32 = lambda d, o: struct.unpack_from("<I", d, o)[0]

def components(path):
    b = open(path, "rb").read(); assert u32(b, 0) == 0x7e5a5a60, "not an FWD package"
    off, size = u32(b, 84), u32(b, 88); pk = b[off:off + size]; out = {}
    for i in range(pk[70]):
        o = 80 + i * 128; st, sz = u32(pk, o + 4), u32(pk, o + 8); name = pk[o + 12:o + 128].split(b"\0")[0].decode()
        z = zipfile.ZipFile(io.BytesIO(pk[st:st + sz])); out[name] = z.read(z.namelist()[0])
    return out

if __name__ == "__main__":
    c = components(sys.argv[1]); cmd = sys.argv[2]
    if cmd == "list": [print("%9d %s" % (len(v), k)) for k, v in c.items()]
    elif cmd == "main": open(sys.argv[3], "wb").write(c[MAIN])
    elif cmd == "get": open(sys.argv[4], "wb").write(c[sys.argv[3]])
    else: sys.exit(__doc__)
