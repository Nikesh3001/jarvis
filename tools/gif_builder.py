import os, math, struct
from pathlib import Path
from core.ratelimit import check_rate


class GIFBuilder:
    def __init__(self, width=128, height=128, fps=10):
        self.width = width
        self.height = height
        self.delay = max(1, int(100 / fps))
        self.frames = []

    def add_frame(self, pixels):
        self.frames.append(list(pixels))

    def add_frames(self, frames_list):
        for f in frames_list:
            self.add_frame(f)

    def _color_table(self, pixels, num_colors=64):
        color_map = {}
        for frame in self.frames:
            for row in frame:
                for r, g, b in row:
                    quantized = ((r // 32) * 32, (g // 32) * 32, (b // 32) * 32)
                    color_map[quantized] = color_map.get(quantized, 0) + 1
        sorted_colors = sorted(color_map.keys(), key=lambda c: -color_map[c])
        palette = sorted_colors[:num_colors]
        while len(palette) < num_colors:
            palette.append((0, 0, 0))
        return palette[:256]

    def save(self, output_path, num_colors=64, optimize_for_emoji=True, remove_duplicates=True):
        if not self.frames:
            raise ValueError("No frames to save")

        if remove_duplicates:
            deduped = [self.frames[0]]
            for f in self.frames[1:]:
                if f != deduped[-1]:
                    deduped.append(f)
            self.frames = deduped

        palette = self._color_table(self.frames, num_colors)

        output_path = str(output_path)
        with open(output_path, "wb") as f:
            self._write_header(f, palette)
            for i, frame in enumerate(self.frames):
                delay = max(1, self.delay // 10) if optimize_for_emoji else self.delay
                self._write_frame(f, frame, palette, delay, i == 0)
            self._write_trailer(f)

    def _write_header(self, f, palette):
        f.write(b"GIF89a")
        f.write(struct.pack("<HH", self.width, self.height))
        packed = 0xF0 | (len(palette) - 1).bit_length() - 1 if len(palette) > 2 else 0x70
        f.write(struct.pack("B", packed))
        f.write(b"\x00\x00")
        for color in palette:
            f.write(bytes(color))
        remaining = 256 - len(palette)
        f.write(b"\x00" * remaining * 3)

    def _write_frame(self, f, frame, palette, delay, is_first):
        if is_first:
            f.write(b"\x21\xFF\x0BNETSCAPE2.0\x03\x01\x00\x00\x00")

        f.write(b"\x21\xF9\x04")
        disposal = 0x02 if not is_first else 0x00
        f.write(struct.pack("BB", disposal | 0x00, delay & 0xFF))
        f.write(struct.pack("B", (delay >> 8) & 0xFF))
        f.write(b"\x00\x00")

        left, top = 0, 0
        f.write(b"\x2C")
        f.write(struct.pack("<HHHH", left, top, self.width, self.height))
        packed = 0x80 | ((len(palette) - 1).bit_length() - 1) if len(palette) > 2 else 0x00
        f.write(struct.pack("B", packed))

        raw = bytearray()
        for y in range(self.height):
            for x in range(self.width):
                r, g, b = frame[y][x]
                best = 0
                best_dist = float("inf")
                for pi, pc in enumerate(palette):
                    dr, dg, db = r - pc[0], g - pc[1], b - pc[2]
                    dist = dr * dr + dg * dg + db * db
                    if dist < best_dist:
                        best_dist = dist
                        best = pi
                raw.append(best)

        from io import BytesIO
        buf = BytesIO()
        code_size = max(2, (len(palette) - 1).bit_length())
        self._lzw_encode(raw, buf, code_size)
        compressed = buf.getvalue()

        f.write(struct.pack("B", code_size))
        offset = 0
        while offset < len(compressed):
            chunk = compressed[offset:offset + 255]
            f.write(struct.pack("B", len(chunk)))
            f.write(chunk)
            offset += 255
        f.write(b"\x00")

    def _lzw_encode(self, data, buf, min_code_size):
        clear_code = 1 << min_code_size
        eoi_code = clear_code + 1
        next_code = eoi_code + 1

        table = {}
        for i in range(clear_code):
            table[bytes([i])] = i

        string = bytes([data[0]])
        bit_buf = 0
        bit_count = 0
        code_size = min_code_size + 1

        def write_code(code):
            nonlocal bit_buf, bit_count
            bit_buf |= code << bit_count
            bit_count += code_size
            while bit_count >= 8:
                buf.write(bytes([bit_buf & 0xFF]))
                bit_buf >>= 8
                bit_count -= 8

        write_code(clear_code)

        for byte in data[1:]:
            symbol = bytes([byte])
            new_string = string + symbol
            if new_string in table:
                string = new_string
            else:
                write_code(table[string])
                if next_code < 4096:
                    table[new_string] = next_code
                    next_code += 1
                    if next_code > (1 << code_size) and code_size < 12:
                        code_size += 1
                string = symbol

        if string:
            write_code(table[string])

        write_code(eoi_code)
        if bit_count > 0:
            buf.write(bytes([bit_buf & 0xFF]))

    def _write_trailer(self, f):
        f.write(b"\x3B")

    def get_tool_definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "create_gif",
                    "description": "Create an animated GIF from frame descriptions. Describe frames as pixel grids or use draw helpers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "frames_description": {
                                "type": "string",
                                "description": "Description of frames to generate (pixel colors per frame)"
                            },
                            "output_path": {
                                "type": "string",
                                "description": "Path to save the GIF file"
                            },
                            "width": {"type": "integer", "description": "Width in pixels", "default": 128},
                            "height": {"type": "integer", "description": "Height in pixels", "default": 128},
                            "fps": {"type": "integer", "description": "Frames per second", "default": 10},
                            "num_colors": {"type": "integer", "description": "Number of colors in palette", "default": 64},
                        },
                        "required": ["frames_description", "output_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_gif",
                    "description": "Analyze an existing GIF file for metadata, frame count, dimensions, and optimization suggestions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path to GIF file"}
                        },
                        "required": ["path"]
                    }
                }
            }
        ]

    def get_handler(self, name):
        handlers = {"create_gif": self._handle_create_gif, "analyze_gif": self._handle_analyze_gif}
        return handlers.get(name)

    def _handle_create_gif(self, frames_description="", output_path="", width=128, height=128, fps=10, num_colors=64):
        if not check_rate("gif:create", rate=5, burst=10):
            return "Rate limited"
        if not frames_description or not output_path:
            return "frames_description and output_path required"
        try:
            from core.brain import _sanitize_error as _se
            import ast

            frame_data = ast.literal_eval(frames_description) if frames_description.startswith("[") else None

            if frame_data and isinstance(frame_data, list):
                from PIL import Image
                builder = GIFBuilder(width, height, fps)
                for fdata in frame_data:
                    img = Image.new("RGB", (width, height))
                    pixels = img.load()
                    for y, row in enumerate(fdata):
                        for x, color in enumerate(row):
                            if x < width and y < height:
                                pixels[x, y] = tuple(color[:3])
                    builder.add_frame(list(list(r) for r in list(img.getdata())))
                builder.save(output_path, num_colors=num_colors)
                return f"GIF saved to {output_path} ({len(builder.frames)} frames)"
            else:
                return "GIF creation requires a list-of-lists pixel description. Use Python list literal format."
        except Exception as e:
            err = str(e)[:200]
            return f"[GIF Error] {err}"

    def _handle_analyze_gif(self, path=""):
        if not check_rate("gif:analyze", rate=10, burst=20):
            return "Rate limited"
        if not path or not os.path.isfile(path):
            return f"File not found: {path}"
        try:
            with open(path, "rb") as f:
                data = f.read()
                if data[:3] != b"GIF":
                    return "Not a valid GIF file"
                version = data[3:6].decode()
                width, height = struct.unpack("<HH", data[6:10])
                frame_count = 0
                for i in range(len(data)):
                    if data[i] == 0x2C and i + 9 < len(data):
                        if i == 0 or data[i-1] != 0x80:
                            frame_count += 1
            if frame_count == 0:
                frame_count = data.count(b"\x2C")
            kb = os.path.getsize(path) / 1024
            return f"GIF {version}: {width}x{height}, {frame_count} frames, {kb:.1f} KB"
        except Exception as e:
            return f"[Analysis Error] {str(e)[:200]}"
