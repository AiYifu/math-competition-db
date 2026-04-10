import os

d = r"C:\竞赛helper\OCR结果"
files = os.listdir(d)

print("="*70)
print("所有书籍文本提取结果概览")
print("="*70)

for f in sorted(files):
    path = os.path.join(d, f)
    size_kb = os.path.getsize(path) / 1024
    with open(path, "r", encoding="utf-8") as file:
        lines = sum(1 for _ in file)
    print(f"\n书名: {f}")
    print(f"  大小: {size_kb:.1f} KB")
    print(f"  行数: {lines} 行")

print(f"\n共 {len(files)} 个文件")
print(f"\n输出目录: {d}")
