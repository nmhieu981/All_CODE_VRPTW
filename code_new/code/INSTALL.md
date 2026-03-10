# Hướng dẫn cài đặt và chạy thuật toán iNSSSO cho MO-VRPTW

## Yêu cầu hệ thống
- Python >= 3.9

## Các thư viện sử dụng

| Thư viện | Phiên bản | Mục đích |
|----------|-----------|----------|
| `numpy` | >= 1.24.0 | Tính toán vector, ma trận, random-key encoding |
| `scipy` | >= 1.10.0 | Tính khoảng cách Euclid (`cdist`) |
| `matplotlib` | >= 3.7.0 | Vẽ biểu đồ Pareto, route, convergence |
| `pandas` | >= 2.0.0 | Xuất kết quả CSV, xử lý bảng dữ liệu |
| `pyyaml` | >= 6.0 | Đọc file cấu hình `config/params.yaml` |
| `pymoo` | >= 0.6.0 | Tính Hypervolume (có fallback Monte-Carlo nếu không cài) |

## Cài đặt

### 1. Tạo môi trường ảo (Virtual Environment)

```bash
cd g:\BaoCaoLuanVanThs\code
python -m venv venv
```

### 2. Kích hoạt môi trường ảo

**Windows:**
```bash
.\venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 3. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

## Cách chạy

### Chạy 1 instance
```bash
python main.py --mode single --instance C101 --time 30
```

### So sánh 6 thuật toán trên 1 instance
```bash
python main.py --mode compare --instance C101 --time 60 --runs 15
```

### Chạy toàn bộ 56 instances Solomon
```bash
python run_all.py
```

### Tham số có thể tùy chỉnh
- `--instance`: tên instance (C101, R201, RC108,...)
- `--time`: thời gian chạy mỗi instance (giây)
- `--runs`: số lần chạy lặp lại (cho so sánh thống kê)

## Cấu trúc thư mục

```
code/
├── core/               # Biểu diễn bài toán & lời giải
├── algorithm/          # Thuật toán iNSSSO, NSSSO, ABS, heuristics
├── comparison/         # Các thuật toán so sánh (NSGA-II, MOPSO, MOEA/D, SPEA2)
├── benchmark/          # Metrics đánh giá (HV, IGD, Coverage)
├── visualization/      # Vẽ biểu đồ
├── config/             # File cấu hình YAML
├── data/               # Dữ liệu Solomon benchmark
├── results/            # Kết quả đầu ra
├── main.py             # Entry point chính
├── run_all.py          # Chạy toàn bộ instances
└── requirements.txt    # Danh sách thư viện
```
