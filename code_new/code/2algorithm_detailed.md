# Thuật toán iNSSSO cho bài toán MO-VRPTW — Tài liệu Chi tiết

> **Tài liệu phục vụ viết bài báo Q1**
> Mã nguồn: [code](file:///g:/BaoCaoLuanVanThs/code_new/code)

---

## 1. Phát biểu Bài toán (Problem Formulation)

### 1.1. Bài toán MO-VRPTW

**Vehicle Routing Problem with Time Windows (VRPTW)** là bài toán tối ưu tổ hợp NP-hard kinh điển trong logistics. Cho $n$ khách hàng và 1 kho (depot), mỗi khách hàng $i$ có:
- Tọa độ $(x_i, y_i)$
- Nhu cầu hàng hóa $q_i$
- Cửa sổ thời gian $[e_i, l_i]$: chỉ được bắt đầu phục vụ trong khoảng này
- Thời gian phục vụ $s_i$

Đội xe gồm $K$ xe đồng nhất, mỗi xe có tải trọng tối đa $Q$. Mỗi xe xuất phát từ depot, phục vụ một tập khách hàng, rồi quay về depot.

### 1.2. Ba mục tiêu tối ưu (đều cực tiểu hóa)

#### Mục tiêu 1: Tổng quãng đường — $f_1$

$$f_1 = \sum_{k=1}^{K} \sum_{(i,j) \in \text{route}_k} d_{ij}$$

**Ý nghĩa:** Tối thiểu hóa chi phí vận chuyển. Đây là mục tiêu phổ biến nhất trong VRP — liên quan trực tiếp đến chi phí nhiên liệu, thời gian lái xe, và khí thải CO₂. Trong thực tế, giảm 1% quãng đường có thể tiết kiệm hàng triệu đồng cho các công ty logistics.

#### Mục tiêu 2: Sự bất mãn khách hàng — $f_2$

$$f_2 = \frac{1}{n} \sum_{k=1}^{K} \sum_{i \in \text{route}_k} w_i, \quad w_i = \max(0, \; e_i - a_i)$$

**Ý nghĩa:** Thời gian chờ $w_i$ xảy ra khi xe đến sớm ($a_i < e_i$), phải chờ đến $e_i$ mới được phục vụ. Thời gian chờ lớn → xe bị "nhàn rỗi" → lãng phí nguồn lực. Tuy nhiên, nếu tối ưu $f_1$ quá mạnh (đường đi ngắn nhất), xe sẽ chạy nhanh đến các khách hàng gần nhau dù phải chờ lâu. $f_2$ cân bằng điều này — khuyến khích lộ trình "vừa đủ" về thời gian.

> [!NOTE]
> $f_2$ là **trung bình** thời gian chờ (chia cho $n$), không phải tổng. Điều này giúp $f_2$ không phụ thuộc vào kích thước bài toán, dễ so sánh giữa các instance.

#### Mục tiêu 3: Độ lệch tải trọng công việc — $f_3$

$$f_3 = \frac{1}{|\sigma|} \sum_{k \in \sigma} \frac{T_{\max} - T_k}{T_{\max}}$$

trong đó $T_k$ là thời gian hoàn thành route $k$, $T_{\max} = \max_k T_k$, $\sigma$ = tập xe được sử dụng.

**Ý nghĩa:** Đảm bảo công bằng giữa các tài xế. Nếu một xe chạy 8 tiếng trong khi xe khác chỉ chạy 2 tiếng → bất công. $f_3 = 0$ khi tất cả route có cùng $T_k$ (hoàn toàn cân bằng). $f_3$ gần 1 khi hầu hết route rất ngắn so với route dài nhất.

**Công thức thay thế (Eq. 5):** $f_3 = \sum_k |T_k - T_{\text{avg}}|$ — tổng độ lệch tuyệt đối so với trung bình. Dùng khi muốn phạt cả route dài lẫn route ngắn bất thường.

### 1.3. Ràng buộc cứng

| Ràng buộc | Công thức | Ý nghĩa thực tế |
|-----------|-----------|------------------|
| **Tải trọng** | $\sum_{i \in \text{route}_k} q_i \leq Q$ | Xe không được chở quá tải |
| **Cửa sổ thời gian** | $\max(a_i, e_i) \leq l_i$ | Phải đến trước giờ đóng cửa |
| **Quay về depot** | $T_k \leq l_0$ | Xe phải về kho trước giờ đóng |

**Xử lý vi phạm:** Khách hàng vi phạm bị đưa vào danh sách `unassigned`. Mỗi khách hàng chưa được phục vụ bị phạt $P = 10^4$ cộng vào mỗi mục tiêu → thuật toán ưu tiên phục vụ tất cả trước khi tối ưu.

### 1.4. Tại sao đa mục tiêu?

Ba mục tiêu **mâu thuẫn** với nhau:
- Tối ưu $f_1$ (đường ngắn) → xe phục vụ cụm khách gần nhau → một số xe rất bận, một số rất nhàn → $f_3$ tăng
- Tối ưu $f_2$ (ít chờ) → xe đến đúng lúc → có thể phải đi đường vòng → $f_1$ tăng
- Tối ưu $f_3$ (cân bằng) → chia đều công việc → route không theo cụm tối ưu → $f_1$ tăng

Do đó, không tồn tại lời giải tối ưu duy nhất, mà tồn tại một **tập Pareto** — tập các lời giải mà không lời giải nào tốt hơn ở TẤT CẢ mục tiêu.

---

## 2. Biểu diễn Lời giải (Solution Encoding)

### 2.1. Random-Key Encoding — Tại sao?

**Vấn đề:** VRPTW là bài toán tổ hợp rời rạc (thứ tự khách hàng + phân chia xe). Nhưng SSO (Squirrel Search Optimization) là thuật toán hoạt động trên **không gian liên tục** $\mathbb{R}^n$.

**Giải pháp:** Dùng **mã hóa khóa ngẫu nhiên (Random-Key)** — mỗi lời giải là vector thực $X = (x_1, \ldots, x_{n_{\text{var}}}) \in [0,1)^{n_{\text{var}}}$, với:

$$n_{\text{var}} = n + K - 1$$

- $n$ vị trí cho $n$ khách hàng
- $K - 1$ vị trí cho $K - 1$ dấu phân cách giữa các route (cần $K-1$ ngăn cách cho $K$ route)

**Ưu điểm:**
1. SSO, polynomial mutation hoạt động trực tiếp trên vector thực — không cần toán tử hoán vị phức tạp
2. Mọi vector $[0,1)^{n_{\text{var}}}$ đều decode được → không có lời giải "bất hợp lệ" ở mức cấu trúc
3. Dễ perturbation bằng cộng nhiễu Gaussian

### 2.2. Quá trình Decode

**Bước 1 — Sắp xếp:** Tính chỉ số sắp xếp $Z = \text{argsort}(X) + 1$

**Bước 2 — Phân loại:**
- Giá trị $z \leq n$ = **ID khách hàng**
- Giá trị $z > n$ = **dấu phân cách route**

**Bước 3 — Xây dựng route:** Các khách hàng giữa 2 dấu phân cách liên tiếp thuộc cùng 1 route

**Ví dụ minh họa** ($n = 5$ khách hàng, $K = 3$ xe):

```
Vị trí:        1     2     3     4     5     6     7
Keys X:      [0.32, 0.85, 0.14, 0.67, 0.91, 0.43, 0.58]
                                                         
Sắp xếp tăng dần: 0.14 < 0.32 < 0.43 < 0.67 < 0.58 không...
Z = argsort + 1:   [3,    1,    6,    4,    7,    2,    5]

Phân loại (n=5):
  z=3 → khách hàng 3
  z=1 → khách hàng 1  
  z=6 → PHÂN CÁCH (>5) ───── cắt route
  z=4 → khách hàng 4
  z=7 → PHÂN CÁCH (>5) ───── cắt route  
  z=2 → khách hàng 2
  z=5 → khách hàng 5

Kết quả: Route 1: [3, 1] | Route 2: [4] | Route 3: [2, 5]
```

**Ý nghĩa:** Thứ tự của keys quyết định thứ tự phục vụ. Key nhỏ → xuất hiện sớm trong chuỗi Z → được phục vụ trước. Dấu phân cách (giá trị > n) tự nhiên chia chuỗi thành các route.

### 2.3. Reverse Encoding — Từ route ngược về keys

Khi ta có một tập route tốt (ví dụ từ Clarke-Wright), cần chuyển ngược về vector keys để SSO có thể hoạt động:

$$\text{keys}[z_i - 1] \sim \mathcal{U}\left(\frac{i}{n_{\text{var}}}, \frac{i+1}{n_{\text{var}}}\right)$$

**Ý nghĩa:** Vị trí thứ $i$ trong chuỗi Z nhận key nằm trong khoảng $[i/n_{\text{var}}, (i+1)/n_{\text{var}})$. Điều này đảm bảo argsort sẽ tái tạo đúng chuỗi Z, đồng thời thêm tính ngẫu nhiên nhỏ (uniform trong mỗi khoảng) để tránh keys trùng lặp.

### 2.4. Sửa chữa tính khả thi (Feasibility Repair)

Sau khi decode, **SolutionParser** duyệt từng route tuần tự:

```
Với mỗi khách hàng i trong route:
  1. Kiểm tra tải: load + q_i ≤ Q?
  2. Tính thời gian đến: a_i = t_hiện_tại + t_{prev,i}
  3. Thời gian bắt đầu: start = max(a_i, e_i)
  4. Kiểm tra TW: start ≤ l_i?
  5. Kiểm tra depot: start + s_i + t_{i,0} ≤ l_0?
  → Vi phạm bất kỳ: đưa i vào "unassigned"
```

**Tại sao tuần tự?** Vì thời gian đến phụ thuộc vào khách hàng trước đó — không thể kiểm tra song song. Một khách hàng bị loại ở giữa route sẽ thay đổi thời gian của tất cả khách hàng phía sau.

---

## 3. Mô hình Ưu tiên (Preference Model)

### 3.1. Tại sao cần Preference?

Trong tối ưu đa mục tiêu truyền thống (NSGA-II, SPEA2), thuật toán trả về **toàn bộ Pareto front** — có thể hàng trăm lời giải. Người ra quyết định (DM) phải tự chọn.

**Vấn đề thực tế:**
1. Pareto front của MO-VRPTW 3 mục tiêu là một **mặt** trong không gian 3D — rất khó trực quan hóa
2. DM thường đã có preference: "tôi muốn quãng đường khoảng 830, chấp nhận chờ 0.5 phút, cân bằng tốt"
3. Tài nguyên tính toán có hạn — thay vì dàn trải trên toàn bộ PF, nên **tập trung vào vùng DM quan tâm**

**Giải pháp:** Preference-Based Optimization — hướng tìm kiếm về phía vùng DM muốn, đồng thời vẫn duy trì đa dạng.

### 3.2. Cấu trúc Preference

| Tham số | Ký hiệu | Ví dụ | Ý nghĩa |
|---------|---------|-------|----------|
| **Điểm tham chiếu** | $g = [g_1, g_2, g_3]$ | $[830, 0.5, 0.15]$ | "Tôi mong muốn quãng đường ~830, chờ ~0.5, cân bằng ~0.15" |
| **Vector trọng số** | $w = [w_1, w_2, w_3]$ | $[0.5, 0.3, 0.2]$ | "Quãng đường quan trọng nhất (50%), rồi đến thời gian chờ (30%)" |
| **Bán kính ROI** | $\delta$ | $0.1$ | "Tôi chấp nhận sai lệch 10% quanh g" |

### 3.3. Achievement Scalarizing Function (ASF) — Chi tiết

$$\text{ASF}(x, g, w) = \max_{i=1}^{3} \left\{ w_i \cdot (f_i(x) - g_i) \right\}$$

**Giải thích trực quan:** ASF đo "mức độ vi phạm tệ nhất" so với điểm mong muốn $g$, có tính trọng số.

**Ví dụ cụ thể:** Với $g = [830, 0.5, 0.15]$, $w = [0.5, 0.3, 0.2]$:

| Lời giải | $f_1$ | $f_2$ | $f_3$ | $w_1(f_1-g_1)$ | $w_2(f_2-g_2)$ | $w_3(f_3-g_3)$ | ASF |
|----------|-------|-------|-------|-----------------|-----------------|-----------------|-----|
| A | 835 | 0.4 | 0.20 | 2.5 | -0.03 | 0.01 | **2.5** |
| B | 832 | 0.8 | 0.14 | 1.0 | 0.09 | -0.002 | **1.0** |
| C | 828 | 0.5 | 0.16 | -1.0 | 0.0 | 0.002 | **0.002** |

→ Lời giải C có ASF nhỏ nhất (gần $g$ nhất theo trọng số) → được ưu tiên.

**Augmented ASF** thêm số hạng tổng $\rho \sum w_i(f_i - g_i)$ với $\rho = 10^{-3}$ để phá vỡ trường hợp hòa khi max bằng nhau.

**4 vai trò trong thuật toán:**
1. **Chọn gBest:** Trong Pareto front rank-0, chọn lời giải có ASF nhỏ nhất làm leader cho SSO → hướng toàn bộ quần thể về phía $g$
2. **Cắt tỉa Archive:** Khi archive đầy (>200), loại bỏ lời giải có ASF lớn nhất → giữ lại những lời giải gần $g$ nhất
3. **Phát hiện trì trệ:** Nếu $\min(\text{ASF})$ không cải thiện qua 5 thế hệ → tăng ABS probability, tăng mutation
4. **Theo dõi hội tụ:** Log $\min(\text{ASF})$ mỗi thế hệ thay vì IGD (vì IGD cần true Pareto front)

### 3.4. Region of Interest (ROI)

$$\text{ROI}: \quad \sum_{i=1}^{3} \left( \frac{w_i \cdot (f_i(x) - g_i)}{\delta \cdot (\text{nadir}_i - \text{ideal}_i)} \right)^2 \leq 1$$

**Ý nghĩa hình học:** ROI là một **hyper-ellipsoid** (elip trong không gian 3D) xung quanh điểm $g$:
- Trục dài/ngắn theo trọng số $w_i$ — mục tiêu quan trọng hơn có trục ngắn hơn (ít dung sai)
- Kích thước tỷ lệ với $\delta$ — $\delta$ nhỏ → vùng hẹp, tập trung; $\delta$ lớn → vùng rộng
- Chuẩn hóa bởi $(\text{nadir}_i - \text{ideal}_i)$ — để vùng ROI có kích thước tương đối, không phụ thuộc đơn vị

**Vai trò:** Dùng trong R-Dominance để phân biệt lời giải "trong vùng quan tâm" vs "ngoài vùng". Cũng dùng làm metric đánh giá (ROI Count, R-HV).

### 3.5. Auto-Calibration — Tự động hiệu chỉnh $g$

**Vấn đề:** DM có thể đặt $g$ không hợp lý (quá tham hoặc quá dễ). Nếu $g$ quá tốt → không lời giải nào gần $g$ → ASF luôn dương lớn → preference vô nghĩa.

**Giải pháp:** Tự động tính $g$ từ quần thể ban đầu:

$$g_i = \text{ideal}_i + 0.1 \times \max(p_{10,i} - \text{ideal}_i, \; 0)$$

- $\text{ideal}_i$ = giá trị tốt nhất mục tiêu $i$ trong quần thể (chỉ tính lời giải khả thi)
- $p_{10,i}$ = phân vị thứ 10 (gần tốt nhất, nhưng không phải outlier)
- Hệ số 0.1 = "hơi nới lỏng so với lý tưởng"

**Ví dụ:** Nếu best distance = 825, phân vị 10 = 835 → $g_1 = 825 + 0.1 \times (835 - 825) = 826$. Đây là mức kỳ vọng "tham nhưng khả thi".

**Đảm bảo:** $g_i \geq \text{ideal}_i + 0.01 \times \text{range}_i$ — $g$ luôn cao hơn ideal ít nhất 1% range để ASF có gradient rõ ràng.

---

## 4. Khởi tạo Quần thể (Population Initialization)

### 4.1. Triết lý thiết kế

**Nguyên tắc:** "Chất lượng khởi tạo quyết định trần hiệu suất." Nếu quần thể ban đầu quá tệ, thuật toán tiến hóa cần nhiều thế hệ mới hội tụ (nhưng time budget có hạn, ví dụ 30–60s). Do đó, đầu tư thời gian cho khởi tạo là **có lợi**.

**Cân bằng Exploitation vs Exploration:**
- **33% heuristic seeds** (chất lượng cao) → cho thuật toán điểm khởi đầu tốt gần lời giải tối ưu
- **67% random** (đa dạng cao) → đảm bảo quần thể phủ rộng không gian tìm kiếm, tránh bị kẹt ở vùng cục bộ

### 4.2. Tier 1: [best_initialization()](file:///g:/BaoCaoLuanVanThs/code_new/code/algorithm/init_heuristics.py#578-643) — Tạo lời giải tinh hoa

**Ngân sách thời gian:** $\min(40\% \times t_{\text{run}}, 15\text{s})$

#### Phase 1: Tạo ứng viên từ 8 heuristic (nhanh, không LS)

Chạy song song 8 chiến lược xây dựng:

| # | Chiến lược | Thuật toán | Tại sao cần? |
|---|------------|------------|--------------|
| 1 | **CW** | Clarke-Wright Savings | Tốt nhất cho giảm số xe (gộp route tiết kiệm nhất) |
| 2 | **NN** | Nearest Neighbour | Nhanh, cho route chặt về khoảng cách cục bộ |
| 3 | **INS-due** | Insertion (deadline) | Ưu tiên khách hàng gấp → ít vi phạm TW |
| 4 | **INS-ready** | Insertion (ready time) | Theo thứ tự thời gian → ít chờ ($f_2$ tốt) |
| 5 | **INS-demand** | Insertion (demand ↓) | Xếp hàng nặng trước → sử dụng tải hiệu quả |
| 6 | **INS-dist** | Insertion (distance) | Khách gần depot trước → route ngắn |
| 7 | **INS-angle** | Insertion (góc cực) | Chia theo hướng → cluster tự nhiên |
| 8 | **INS-tw** | Insertion (TW center) | Cân bằng thời gian → $f_3$ tốt |

**Ý nghĩa đa dạng:** Mỗi sort key sinh ra **cấu trúc route hoàn toàn khác nhau**. Ví dụ, INS-angle tạo route hình quạt từ depot, trong khi INS-ready tạo route theo dòng thời gian.

#### Phase 2: Full Local Search cho top-2

Sắp xếp 8 ứng viên theo tổng quãng đường, chọn **2 tốt nhất**, áp dụng Local Search đầy đủ gồm:
1. 2-opt + Or-opt (tối ưu từng route)
2. Relocate + Swap + Cross-Exchange (tối ưu giữa các route)
3. Ruin-and-Recreate (phá hủy/tái tạo để thoát cực trị cục bộ)

**Tại sao chỉ top-2?** LS rất tốn thời gian. Áp dụng cho tất cả 8 sẽ vượt ngân sách. Top-2 là trade-off tốt giữa chất lượng và thời gian.

#### Phase 3: Ruin-and-Recreate lặp

Trên kết quả tốt nhất từ Phase 2, chạy thêm **200 lần** R&R — mỗi lần phá hủy 15–40% khách hàng rồi chèn lại tối ưu. Đây là "đánh bóng" cuối cùng.

### 4.3. Clarke-Wright Savings — Chi tiết

**Ý tưởng cốt lõi:** Mỗi khách hàng ban đầu có 1 route riêng (depot→i→depot). Savings $s_{ij}$ = khoảng cách **tiết kiệm** khi gộp 2 route qua i và j:

$$s_{ij} = d_{0,i} + d_{0,j} - d_{i,j}$$

**Trực quan:** Thay vì đi depot→i→depot→j→depot (2 chuyến), ta đi depot→i→j→depot (1 chuyến). Tiết kiệm = đoạn $d_{0,i} + d_{0,j}$ (không cần quay về depot giữa) trừ đi đoạn $d_{i,j}$ (phải nối i-j).

**Cải tiến:** Kiểm tra **4 hướng gộp** (head-tail, tail-head, tail-tail đảo, head-head đảo) thay vì chỉ 2 như bản gốc → tìm được nhiều cách gộp khả thi hơn.

### 4.4. Sequential Insertion Heuristic — Chi tiết

```
SẮP XẾP khách hàng theo sort_key (ví dụ: due_date tăng dần)
VỚI MỖI khách hàng i (theo thứ tự):
  VỚI MỖI route r hiện có:
    VỚI MỖI vị trí pos trong r:
      Tính chi phí chèn = distance(r có i ở pos) - distance(r gốc)
      Nếu khả thi VÀ chi phí nhỏ nhất → ghi nhận
  Nếu tìm được: chèn i vào vị trí tốt nhất
  Nếu không: tạo route mới chỉ chứa i
```

**6 sort keys** tạo ra lời giải khác nhau vì thứ tự chèn ảnh hưởng mạnh đến cấu trúc route. Khách hàng chèn trước "chiếm chỗ" tốt, khách hàng sau phải chen vào chỗ kém hơn hoặc mở route mới.

### 4.5. Greedy Nearest Neighbour — Chi tiết

```
TRONG KHI còn khách hàng chưa phục vụ:
  MỚI route mới, xuất phát từ depot, t=0, load=0
  LẶP:
    Trong các khách hàng chưa phục vụ & khả thi:
      Tính score(i) = max(arrival_i, ready_i) + 0.5 × distance(prev, i)
      Chọn i có score nhỏ nhất
    Nếu không có ai khả thi → kết thúc route
```

**Ý nghĩa score:** Cân bằng giữa:
- $\max(a_i, e_i)$ = thời gian bắt đầu phục vụ (nhỏ → phục vụ sớm)
- $0.5 \times d_{\text{prev},i}$ = khoảng cách (nhỏ → gần)

Hệ số 0.5 giảm trọng số khoảng cách, ưu tiên phục vụ đúng giờ hơn đi gần.

### 4.6. Perturbation — Tạo biến thể

Mỗi heuristic seed tạo thêm **3 biến thể** bằng cách thêm nhiễu vào keys:

$$x_j^{\text{new}} = \text{clip}(x_j + \varepsilon_j, \; 0, \; 0.999), \quad \varepsilon_j \sim \mathcal{U}(-\sigma, \sigma)$$

| $\sigma$ | Mức nhiễu | Ý nghĩa |
|----------|-----------|----------|
| 0.05 | Nhỏ | Thay đổi nhẹ thứ tự → route gần giống gốc |
| 0.10 | Trung bình | Một số khách hàng đổi route → cấu trúc thay đổi vừa |
| 0.15 | Lớn | Nhiều khách hàng đổi chỗ → route khá khác gốc |

**Ý nghĩa:** Tạo "vùng lân cận" xung quanh mỗi lời giải tốt. SSO sẽ cross-over giữa chúng, khám phá không gian quanh lời giải heuristic.

### 4.7. Smart Route Merging

**Khi áp dụng:** Chỉ khi $\text{avg\_utilization} = \frac{\text{total\_demand}}{K \times Q} < 60\%$ (xe còn dư nhiều tải).

**Quy trình:**
1. Chọn route ngắn nhất (ít khách hàng nhất)
2. Thử chèn từng khách hàng của route đó vào các route khác
3. Nếu tất cả chèn được: xóa route ngắn → giảm 1 xe
4. Kiểm tra: tổng quãng đường tăng ≤ 5%? Nếu có → chấp nhận

**Tại sao threshold 5%?** Giảm 1 xe tiết kiệm chi phí cố định (lương tài xế, khấu hao xe), nên chấp nhận tăng nhẹ quãng đường.

---

## 5. Vòng lặp Tiến hóa Chính (Main Evolutionary Loop)

### 5.1. Chiến lược Hybrid - Tại sao?

| Phương pháp | Ưu điểm | Nhược điểm |
|-------------|---------|------------|
| **Full R-Dominance** | Hướng mạnh về $g$ | $O(N^2)$ chậm, mất đa dạng |
| **Pure Pareto** | Nhanh, đa dạng | Không biết DM muốn gì |
| **Hybrid (đề xuất)** | **Nhanh + có hướng** | Cần cân chỉnh |

**Chiến lược:**
- **Ranking & Selection** dùng Pareto tiêu chuẩn → nhanh, giữ đa dạng
- **gBest** dùng ASF → hướng SSO về phía $g$
- **Archive** dùng ASF tie-breaking → lưu lời giải gần $g$
- **ABS** dùng preference-weighted scoring → xây route thiên về preference

### 5.2. Non-dominated Sorting — Vectorized

**Dominance:** Lời giải $a$ **dominate** $b$ khi $a$ tốt hơn hoặc bằng $b$ ở TẤT CẢ mục tiêu, VÀ tốt hơn nghiêm ngặt ở ÍT NHẤT 1 mục tiêu.

**Triển khai NumPy broadcasting:**
```python
a = objectives[:, np.newaxis, :]  # (N, 1, M) — mỗi a so với tất cả b
b = objectives[np.newaxis, :, :]  # (1, N, M)
dom[i,j] = (a[i] ≤ b[j]).all() AND (a[i] < b[j]).any()
```

**Ma trận dom (N×N):** `dom[i][j] = True` ⟺ lời giải $i$ dominate lời giải $j$.

**Front decomposition:**
- Front 0 (rank 0): lời giải không bị ai dominate → **Pareto front**
- Front 1 (rank 1): lời giải chỉ bị front 0 dominate
- ...

### 5.3. Crowding Distance — Giữ đa dạng

**Vấn đề:** Trong cùng một front, lời giải nào tốt hơn? → Ưu tiên lời giải ở **vùng thưa** (ít bị nhau chồng chéo).

**Cách tính:** Với mỗi mục tiêu, sắp xếp lời giải trong front, tính khoảng cách giữa 2 lời giải lân cận:

$$\text{CD}_i = \sum_{m=1}^{M} \frac{f_m^{i+1} - f_m^{i-1}}{f_m^{\max} - f_m^{\min}}$$

- Lời giải ở **biên** (min hoặc max theo bất kỳ mục tiêu nào) có CD = $\infty$ → luôn được giữ
- Lời giải ở **vùng thưa** có CD lớn → được ưu tiên
- **Chuẩn hóa** mỗi mục tiêu về $[0,1]$ trước khi tính → tránh mục tiêu có scale lớn chi phối

### 5.4. gBest Selection — Chọn lãnh đạo

**Binary tournament** trên Pareto front (rank-0):
1. Chọn ngẫu nhiên 2 lời giải từ front 0
2. So sánh:
   - **Ưu tiên 1:** Ít xe hơn → thắng (nếu có route_counts)
   - **Ưu tiên 2 (có preference):** ASF nhỏ hơn → thắng
   - **Ưu tiên 2 (không preference):** CD lớn hơn → thắng

**Ý nghĩa:** gBest là "kim chỉ nam" của SSO. Chọn gBest có ASF nhỏ nhất = hướng tất cả lời giải về phía vùng $g$ muốn.

### 5.5. SSO Update — Cở chế cập nhật Squirrel Search

$$x_{i,j}^{\text{new}} = \begin{cases}
g_{\text{best},j} & \text{với xác suất } c_g = 0.95 \\
x_{i,j} & \text{với xác suất } c_w - c_g = 0.04 \\
\mathcal{U}(0,1) & \text{với xác suất } 1 - c_w = 0.01
\end{cases}$$

**Trực quan (mô phỏng sóc bay):**
- **95% thời gian:** Sóc $i$ bay đến vị trí của sóc tốt nhất (copy key từ gBest) → **khai thác mạnh**
- **4% thời gian:** Sóc $i$ đứng yên (giữ key hiện tại) → **bảo toàn thông tin**
- **1% thời gian:** Sóc $i$ bay đến vị trí ngẫu nhiên → **khám phá** (thoát cực trị cục bộ)

**Tại sao $c_g = 0.95$ rất cao?** Vì VRPTW là bài toán rất khó — cần khai thác mạnh vùng tốt. Với random-key encoding, copy 95% key từ gBest ≈ "giữ lại hầu hết thứ tự khách hàng của lời giải tốt nhất, chỉ thay đổi một vài vị trí."

### 5.6. Polynomial Mutation — Đa dạng hóa

**Khi nào áp dụng?** Chỉ khi:
1. Thuật toán **trì trệ** (stagnation > 3 thế hệ): không cải thiện ASF
2. Xác suất $< p_m$ (tăng dần theo thời gian: $0.05 → 0.15$)

**Cơ chế:** Với mỗi key $x_j$, thêm nhiễu $\delta_q$ tuân theo phân phối đa thức (polynomial distribution) với $\eta_m = 20$:
- $\eta_m$ lớn → nhiễu nhỏ, tập trung gần giá trị gốc
- $\eta_m$ nhỏ → nhiễu lớn, spread rộng

**Ý nghĩa:** Khi thuật toán bị kẹt, mutation phá vỡ population đồng nhất bằng cách thêm biến thể nhỏ. $\eta_m = 20$ là giá trị kinh điển từ NSGA-II — tạo mutation đủ nhỏ để không phá hủy solution tốt, nhưng đủ để thoát local optima.

---

## 6. A*-Based Search (ABS) — Local Search có Preference

### 6.1. Tại sao cần ABS?

SSO cập nhật ở mức **random keys** (liên tục) — hiệu quả cho exploration nhưng yếu cho exploitation chi tiết. ABS hoạt động ở mức **route** (rời rạc) — phá hủy route kém, xây lại route mới **theo preference**.

**Vai trò:** ABS là cầu nối giữa "tối ưu liên tục" (SSO) và "tối ưu tổ hợp" (VRP heuristics).

### 6.2. Pha Phá hủy (Destruction)

Hai chiến lược, chọn ngẫu nhiên:

#### Worst Removal (40% xác suất)

Loại bỏ 15–35% khách hàng gây **tốn khoảng cách nhất**:

$$\text{saving}(c_i) = d_{\text{prev}, c_i} + d_{c_i, \text{next}} - d_{\text{prev}, \text{next}}$$

**Trực quan:** $\text{saving}(c_i)$ = khoảng cách tiết kiệm nếu bỏ qua $c_i$ và nối prev-next trực tiếp. Khách hàng có saving lớn = "lạc lõng" so với route → loại bỏ để chèn lại chỗ tốt hơn.

#### Route Removal (60% xác suất)

Loại bỏ $\lfloor |\text{routes}| / 3 \rfloor$ route, xác suất chọn tỷ lệ nghịch với độ dài:

$$P(\text{route } k) \propto \exp\left(-10 \cdot \frac{n_k}{n_{\max}}\right)$$

**Trực quan:** Route ngắn (ít khách hàng) bị chọn nhiều hơn — vì route ngắn thường "thừa" và khách hàng của nó có thể nhét vào route khác, giảm tổng số xe. Hệ số -10 rất lớn → route 1–2 khách hàng gần như chắc chắn bị loại.

### 6.3. Pha Tái tạo (Reconstruction) — Build Route

Xây route mới từ tập khách hàng chưa phân công, chọn khách hàng tiếp theo bằng **composite score có preference**:

#### calVcost — Kiểm tra khả thi

Trả về 0 nếu khả thi, $\infty$ nếu không. Kiểm tra 3 điều kiện: tải trọng, cửa sổ thời gian, quay về depot.

#### calHcost — Ước lượng heuristic (giống A*)

$$h(c_i) = \text{số khách hàng còn lại có thể phục vụ SAU KHI phục vụ } c_i$$

**Ý nghĩa A*:** Giống hàm heuristic trong A* search — ước lượng "tiềm năng mở rộng" của mỗi lựa chọn. Chọn $c_i$ có $h$ cao = "chèn $c_i$ vẫn để lại nhiều lựa chọn cho sau" → tránh bế tắc sớm (dead-end).

#### Composite Score — Kết hợp theo preference

$$f(c_i) = w_1 \cdot \hat{d}(c_i) + w_2 \cdot \hat{\text{tw}}(c_i) + (1 - w_1 - w_2) \cdot \hat{h}(c_i)$$

| Thành phần | Ký hiệu | Ý nghĩa | Liên quan mục tiêu |
|------------|---------|----------|---------------------|
| Khoảng cách | $\hat{d}$ | Gần = tốt → giảm $f_1$ | $f_1$ (distance) |
| TW urgency | $\hat{\text{tw}}$ | TW hẹp = ưu tiên → giảm $f_2$ | $f_2$ (waiting) |
| Reachability | $\hat{h}$ | Nhiều lựa chọn = tốt → cân bằng | $f_3$ (balance) |

**Trọng số $w$ từ preference quyết định ưu tiên:** Nếu $w = [0.5, 0.3, 0.2]$ → ưu tiên chọn khách hàng gần ($f_1$) hơn là chọn theo TW ($f_2$).

#### Roulette-Wheel Selection

Đảo nghịch score (thấp hơn = tốt → xác suất cao hơn), chọn khách hàng theo bánh xe quay.

**Tại sao không chọn tham lam (greedy)?** Roulette-wheel thêm tính ngẫu nhiên → mỗi lần chạy ABS cho kết quả khác nhau → tăng đa dạng.

### 6.4. Post-processing

1. **Regret-2 Insertion:** Cho khách hàng chưa phân được, tìm vị trí chèn tốt nhất và tốt nhì. Khách hàng có chênh lệch (regret) lớn nhất → chèn trước (vì nếu chờ, sẽ mất vị trí tốt duy nhất).
2. **Quick 2-opt:** Đảo đoạn con trong mỗi route nếu cải thiện — chỉ 1 pass (nhanh).

---

## 7. Pipeline Local Search

### 7.1. Intra-Route: 2-opt

**Ý tưởng:** Đảo ngược đoạn $[i, j]$ trong route. Nếu 2 cạnh giao nhau (crossing), đảo sẽ "gỡ" chúng → giảm khoảng cách.

```
Trước: depot → ... → A → B → C → D → ... → depot
Đảo [B,C,D]: depot → ... → A → D → C → B → ... → depot
Nếu d(A,D)+d(B,...) < d(A,B)+d(D,...) → chấp nhận
```

Lặp cho đến khi không tìm được cải thiện (first-improvement).

### 7.2. Intra-Route: Or-opt

**Ý tưởng:** Di chuyển đoạn 1–3 khách hàng liên tiếp sang vị trí khác trong route. Mạnh hơn 2-opt vì không bị ràng buộc "đảo ngược".

### 7.3. Inter-Route: Relocate, Swap, Cross-Exchange

| Operator | Hành động | Ý nghĩa |
|----------|-----------|----------|
| **Relocate** | Chuyển 1 khách từ route A sang route B | Giảm tải route dài, có thể loại bỏ route ngắn |
| **Swap** | Đổi 1 khách giữa 2 route | Cải thiện clustering |
| **Cross-Exchange** | Hoán đổi phần đuôi 2 route | Tái cấu trúc mạnh, có thể cải thiện đáng kể |

### 7.4. Ruin-and-Recreate

**Triết lý:** "Phá hủy có kiểm soát" — khi LS truyền thống bị kẹt (local optima), phá bỏ 1 phần lời giải rồi xây lại. Giống như "đập bỏ 1 phòng trong nhà để xây lại đẹp hơn."

1. **Destroy:** Loại ngẫu nhiên 15–40% khách hàng
2. **Recreate:** Chèn lại theo thứ tự deadline (khách gấp trước)
3. **Iterate:** Lặp 50–200 lần, giữ kết quả tốt nhất

---

## 8. External Archive (ε-Dominance)

### 8.1. Tại sao cần Archive?

**Vấn đề:** Trong (μ+λ) selection, lời giải Pareto-optimal có thể bị mất nếu bị "lấn" bởi nhiều lời giải rank-1 có CD cao. Archive lưu trữ riêng tất cả lời giải non-dominated từ đầu đến cuối.

### 8.2. ε-Dominance — Tại sao?

**Vấn đề:** Archive có thể phình to nếu lưu TẤT CẢ non-dominated. Với 3 mục tiêu, PF là mặt 2D → hàng nghìn lời giải.

**Giải pháp:** Chia không gian mục tiêu thành ô (box) kích thước $\varepsilon = 0.001$. Mỗi ô chỉ giữ 1 lời giải → archive bị bounded.

$$\text{box}(x) = \left\lfloor \frac{f_i(x)}{\varepsilon} \right\rfloor$$

Trong cùng ô: giữ lời giải có **ASF nhỏ hơn** (gần preference hơn). Đây là điểm khác biệt so với ε-dominance tiêu chuẩn (thường giữ lời giải dominate hơn về Pareto).

### 8.3. Archive Injection

Mỗi thế hệ, **1 lời giải ngẫu nhiên từ archive** được thêm vào offspring. Mục đích:
- **Diversity:** Đưa thông tin từ quá khứ vào quần thể hiện tại
- **Elitism:** Đảm bảo lời giải tốt không bị mất hoàn toàn

---

## 9. Điều khiển Tham số Thích ứng (Adaptive Control)

### 9.1. Phát hiện Trì trệ

$$\text{stagnating} \iff |\text{ASF}_{\text{best}}^{(t)} - \text{ASF}_{\text{best}}^{(t-1)}| < 10^{-6} \text{ trong } \geq 5 \text{ thế hệ liên tiếp}$$

**Ý nghĩa:** Nếu lời giải tốt nhất (theo ASF) không cải thiện → quần thể bị kẹt → cần đa dạng hóa mạnh hơn.

### 9.2. Quy tắc Thích ứng

| Tham số | Bình thường | Khi trì trệ | Ý nghĩa |
|---------|------------|--------------|----------|
| $p_{\text{abs}}$ | 0.20 | $\min(0.50, 0.20 + 0.05 \times \text{stag})$ | Tăng ABS → phá-xây nhiều hơn → thoát local optima |
| $p_m$ | 0.05 | $0.05 + 0.10 \times \text{progress}$ | Tăng mutation → thêm biến thể mới |

**Logic:** Giai đoạn đầu (progress ≈ 0) → exploitation mạnh ($p_m$ thấp, ABS ít). Giai đoạn cuối (progress ≈ 1) → exploration mạnh ($p_m$ cao) vì nếu chưa tìm được tốt, cần phá vỡ cấu trúc.

---

## 10. Selection và Duplicate Elimination

### 10.1. (μ + λ) Selection

Gộp quần thể cha ($N$) + offspring ($N$) + 1 archive injection → **chọn $N$ tốt nhất** theo:

1. **Số xe** (ít hơn → tốt) — phản ánh thực tế: mỗi xe = 1 tài xế + chi phí cố định
2. **Duplicate flag** — unique trước, trùng lặp sau
3. **Pareto rank** — thấp hơn → tốt
4. **Crowding distance** — cao hơn → ở vùng thưa → giữ đa dạng

**Tại sao số xe ưu tiên 1?** Trong Solomon benchmark, số xe tối ưu là known — giải có ít xe hơn **cơ bản tốt hơn** bất kể khoảng cách.

### 10.2. Loại trùng lặp

2 lời giải "trùng" nếu TẤT CẢ mục tiêu chênh lệch $< 10^{-6}$. Lời giải trùng bị phạt trong selection → quần thể luôn đa dạng.

---

## 11. R-Dominance (Module có sẵn)

R-Dominance mở rộng Pareto dominance bằng preference:

$$x \text{ R-dominates } y \iff \begin{cases}
x \text{ Pareto-dominates } y, \text{ HOẶC} \\
x \in \text{ROI} \text{ và } y \notin \text{ROI}, \text{ HOẶC} \\
\text{cùng ROI status và } \text{ASF}(x) < \text{ASF}(y)
\end{cases}$$

**Ý nghĩa:** Lời giải trong ROI luôn "thắng" lời giải ngoài ROI, bất kể Pareto dominance. Điều này cực kỳ mạnh trong việc thu hẹp PF về vùng preference.

**Tại sao không dùng trong hybrid?** R-Dominance tạo ma trận $N \times N$ → $O(N^2)$ chậm. Hybrid đạt hiệu quả tương đương bằng cách dùng ASF chỉ ở gBest selection (chỉ xét front-0, nhỏ hơn $N$ nhiều).

---

## 12. Metrics Đánh giá

| Metric | Công thức | Ý nghĩa chi tiết |
|--------|-----------|-------------------|
| **Cov** | $\frac{|\{v \in P^* : \exists v'\preceq v\}|}{|P^*|}$ | Bao nhiêu % PF thật bị PF tìm được dominate → đo **convergence** |
| **IGD** | $\frac{1}{|P^*|}\sum \min \|v-v'\|$ | Trung bình khoảng cách từ PF thật đến PF tìm được → đo **cả convergence lẫn diversity** |
| **HV** | Thể tích bị dominated dưới ref point | Chỉ số duy nhất đo cả **convergence + diversity + spread** cùng lúc |
| **R-HV** | HV chỉ tính trong ROI | HV ở **vùng preference** → đo hiệu quả preference guidance |
| **Best ASF** | $\min \text{ASF}(x)$ | Lời giải **gần $g$ nhất** → đo preference satisfaction |
| **ROI Count** | Số lời giải trong ROI | Bao nhiêu lời giải nằm trong vùng DM quan tâm |
| **Nnds** | Kích thước front-0 | Số lời giải non-dominated → đo **cardinality** của PF |

---

## 13. Tóm tắt Tham số

| Tham số | Giá trị | Ý nghĩa |
|---------|---------|----------|
| $N$ | 100 | Cân bằng giữa diversity và tốc độ |
| $t_{\text{run}}$ | 60s | Thời gian chạy tổng |
| $c_g = 0.95$ | Rất cao | Exploitation mạnh — copy gBest |
| $c_w = 0.99$ | Cao | Ít exploration ngẫu nhiên |
| $p_{\text{abs}} = 0.20$ | Trung bình | 20% lần dùng ABS, 80% dùng SSO |
| Archive = 200 | Vừa | Đủ lưu PF đa dạng |
| $\varepsilon = 0.001$ | Nhỏ | Grid mịn → không mất solution tốt |
| $\delta = 0.10$ | Nhỏ | ROI tập trung sát $g$ |
| $\eta_m = 20$ | Cao | Mutation nhẹ, không phá hủy |

---

## 14. Độ phức tạp

| Thành phần | Chi phí/thế hệ | Ghi chú |
|------------|----------------|---------|
| Non-dominated sort | $O(MN^2)$ | M=3 objectives, N=100 → ~30K ops |
| Crowding distance | $O(MN\log N)$ | Per front |
| SSO update | $O(N \cdot n_{\text{var}})$ | Vectorized, rất nhanh |
| ABS search | $O(p_{\text{abs}} N n^2)$ | Đắt nhất — rebuild $O(n^2)$ |
| Archive update | $O(|A| \cdot N)$ | Pairwise check |
| **Tổng** | **$O(MN^2 + p_{\text{abs}}Nn^2)$** | Với n=100, N=100 → ~200K ops |
