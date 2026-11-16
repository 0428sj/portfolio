# PCD 읽기(binary / binary_compressed) — 필드별 numpy 구조 배열로 반환
import numpy as np


def lzf_decompress(src, out_len):
    out = bytearray(out_len); i = o = 0; n = len(src)
    while i < n:
        c = src[i]; i += 1
        if c < 32:
            L = c + 1; out[o:o + L] = src[i:i + L]; i += L; o += L
        else:
            L = c >> 5
            if L == 7: L += src[i]; i += 1
            ref = o - ((c & 0x1f) << 8) - src[i] - 1; i += 1; L += 2
            for k in range(L): out[o + k] = out[ref + k]
            o += L
    if o != out_len: raise ValueError(f"LZF 길이 불일치 {o} != {out_len}")
    return bytes(out)


def read_pcd(path):
    b = open(path, "rb").read()
    for kind in (b"binary_compressed", b"binary"):
        tag = b"DATA " + kind + b"\n"
        if tag in b[:4096]:
            end = b.index(tag) + len(tag); break
    else:
        raise ValueError("binary/binary_compressed PCD 만 지원")
    H = {l.split()[0]: l.split()[1:] for l in b[:end].decode().splitlines() if l and not l.startswith("#")}
    if any(int(c) != 1 for c in H["COUNT"]): raise ValueError("COUNT>1 미지원")
    dt = [(f, {"F": "f", "U": "u", "I": "i"}[t] + s) for f, s, t in zip(H["FIELDS"], H["SIZE"], H["TYPE"])]
    n = int(H["POINTS"][0])
    if kind == b"binary":
        return np.frombuffer(b[end:], dtype=dt, count=n)
    csz, usz = np.frombuffer(b[end:end + 8], dtype=np.uint32)
    raw = lzf_decompress(b[end + 8:end + 8 + int(csz)], int(usz))
    arr = np.empty(n, dtype=dt); off = 0
    for f, d in dt:  # 압축본은 필드별로 이어 붙여 저장
        k = np.dtype(d).itemsize * n; arr[f] = np.frombuffer(raw[off:off + k], dtype=d); off += k
    return arr


def write_pcd_binary(path, xyz, intensity=None):
    n = len(xyz); it = np.zeros(n, np.float32) if intensity is None else intensity.astype(np.float32)
    arr = np.empty(n, dtype=[("x", "f4"), ("y", "f4"), ("z", "f4"), ("intensity", "f4")])
    arr["x"], arr["y"], arr["z"], arr["intensity"] = xyz[:, 0], xyz[:, 1], xyz[:, 2], it
    hdr = ("# .PCD v0.7\nVERSION 0.7\nFIELDS x y z intensity\nSIZE 4 4 4 4\nTYPE F F F F\nCOUNT 1 1 1 1\n"
           f"WIDTH {n}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS {n}\nDATA binary\n")
    open(path, "wb").write(hdr.encode() + arr.tobytes())
