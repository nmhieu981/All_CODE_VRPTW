# Các bước giải quyết thuật toán iNSSSO cho MO-VRPTW

## **Bước 1: Đọc dữ liệu đầu vào**
- Đọc file Solomon (TXT/CSV): tọa độ depot, tọa độ + demand + time window (`ready_time`, `due_date`, `service_time`) của từng customer
- Tính ma trận khoảng cách Euclid và ma trận thời gian di chuyển giữa tất cả các cặp node (gồm depot)
- Xác định: `n_customers`, `n_vehicles`, `capacity`

---

## **Bước 2: Mã hóa lời giải (Random-Key Encoding)**
- Mỗi lời giải là vector `keys` gồm `nvar = n_customers + n_vehicles - 1` số thực trong `[0, 1)`
- **Giải mã**: sắp xếp `keys` tăng dần → vector thứ tự `Z`. Các giá trị `1..n_customers` là customer, các giá trị `> n_customers` là dấu phân cách giữa các route
- Ví dụ: `Z = [3, 1, 101, 5, 2, 102, 4]` → Route 1: `[3,1]`, Route 2: `[5,2]`, Route 3: `[4]`

---

## **Bước 3: Khởi tạo quần thể (Population Initialization)**
1. **Multi-start heuristic** — tạo nhiều lời giải ban đầu bằng các chiến lược:
   - **Clarke-Wright Savings**: ghép cặp customer có tiết kiệm khoảng cách lớn nhất
   - **Solomon I1 Insertion**: sắp customer theo 6 tiêu chí khác nhau (`due_date`, `ready_time`, `demand`, `distance`, `angle`, `tw_center`), chèn vào vị trí rẻ nhất trong route hiện có
   - **Greedy Nearest Neighbour**: chọn customer gần nhất thỏa time window
2. **Local Search** trên top-2 lời giải tốt nhất:
   - **2-opt** (đảo ngược đoạn trong route)
   - **Or-opt** (di chuyển 1-3 customer trong route)
   - **Inter-route Relocate** (chuyển customer sang route khác)
   - **Inter-route Swap** (đổi customer giữa 2 route)
   - **2-opt\* Cross-exchange** (đổi đuôi giữa 2 route)
   - **Ruin-and-Recreate** (loại 15-40% customer ngẫu nhiên, chèn lại tại vị trí rẻ nhất)
3. **Tạo quần thể** `n_sol = 100` cá thể: lời giải tốt nhất + các biến thể nhiễu + random

---

## **Bước 4: Đánh giá fitness (3 mục tiêu)**
Với mỗi route hợp lệ, tính:
- **f₁** = Tổng khoảng cách tất cả route (minimize)
- **f₂** = Tổng thời gian chờ tại các customer (minimize)
- **f₃** = Độ mất cân bằng tải giữa các route = `max(makespan) - min(makespan)` / `avg(makespan)` (minimize)
- Customer vi phạm ràng buộc (capacity, time window) → penalty cộng vào f₁

---

## **Bước 5: Xếp hạng (Non-dominated Sorting + Crowding Distance)**
1. **Fast Non-dominated Sorting** (Deb 2002): chia quần thể thành các front F₀, F₁, F₂...
   - F₀ = Pareto front (không bị thống trị bởi lời giải nào)
2. **Crowding Distance**: đo khoảng cách giữa các lời giải trong cùng front → đảm bảo đa dạng

---

## **Bước 6: Tạo offspring (SSO Update Rule — Eq. 2)**
Với mỗi cá thể `xᵢ`:
- Chọn `gbest` từ Pareto front (roulette theo crowding distance)
- Với mỗi chiều `j` của vector keys:
  - Sinh `ρ ∈ [0,1]` ngẫu nhiên
  - Nếu `ρ ≤ Cg (0.95)`: lấy key từ `gbest` → **exploitation**
  - Nếu `Cg < ρ ≤ Cw (0.99)`: giữ key cũ → **giữ nguyên**
  - Nếu `ρ > Cw`: sinh key ngẫu nhiên → **exploration**

---

## **Bước 7: A\*-Based Search (ABS) — Local Search**
- Với xác suất `n_abs = 0.2`, thay vì SSO, áp dụng ABS:
  1. Giải mã lời giải hiện tại → danh sách route
  2. Chọn ngẫu nhiên 2 route, trộn customer của chúng
  3. Dùng heuristic chèn greedy để tái cấu trúc thành 2 route tốt hơn
  4. Mã hóa ngược (`from_routes`) thành vector keys mới

---

## **Bước 8: Selection (Merge + Select Best)**
1. Gộp quần thể cũ (100) + offspring (100) = 200 cá thể
2. Non-dominated sorting trên 200 cá thể
3. Chọn 100 cá thể tốt nhất: ưu tiên front thấp → crowding distance cao

---

## **Bước 9: Lặp lại**
- Lặp Bước 5 → 8 cho đến khi hết thời gian `t_run`
- Mỗi vòng lặp = 1 generation

---

## **Bước 10: Trả về kết quả**
- Pareto front cuối cùng (F₀) = tập lời giải không bị thống trị
- Mỗi lời giải gồm: danh sách route, 3 giá trị mục tiêu (f₁, f₂, f₃)
- Xuất: tổng khoảng cách tốt nhất, số route, các biểu đồ (Pareto, route, convergence)
