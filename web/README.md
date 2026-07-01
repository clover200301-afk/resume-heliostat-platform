# 定日镜场在线仿真选址平台

基于 CUMCM 2023A 题的物理引擎（[`../code/engine.py`](../code/engine.py)），把矢量化光学模型包装为一个**面向选址决策**的 Web 应用。

## 功能

- **🗺️ 世界地图选址**（Leaflet 暗色底图）：点击任意位置设定 (lat, lng)。
- **🌐 3D 镜场实时仿真**（Three.js）：500 面定日镜按物理公式实时调整朝向，太阳/塔/集热器/光晕一应俱全。
- **📊 实时指标仪表盘**：太阳高度/方位、DNI、各项效率、瞬时功率、单位面积功率。
- **📈 全年月度曲线**（Chart.js）：12 个月的平均功率 + 光学效率双轴图。
- **🔬 多场地对比**：保存任意多个候选场地（甘肃、拉萨、撒哈拉…），柱状图并列对比年均功率 / ppa。
- **▶ 一天动画**：自动从 5 点播放到日落，看一天中镜面跟随太阳的连续变化。

## 一键启动

```bash
cd web/
uvicorn app:app --reload --port 8000
```

浏览器打开 <http://localhost:8000>。

> 依赖：`fastapi`、`uvicorn`、`numpy`、`scipy`（已在论文章节装好）。前端通过 CDN 加载 Three.js / Leaflet / Chart.js，无需 npm 构建。

## 体验脚本（建议按顺序）

1. 拖动 **时间** 滑块从清晨到日落 → 太阳沿轨迹弧移动，镜面持续调向；
2. 把 **海拔** 从 0 拉到 5 km → DNI 显著上升，年均功率随之增加；
3. 把 **大气清澈度** 从 1.0 拉到 0.5 → 模拟雾霾，DNI 直接减半；
4. 切换 **日期** 至 12/21 → 冬至日太阳偏低，月度柱状条显著矮于 6/21；
5. 在地图上点 拉萨（约 29.6°N, 91.1°E）→ 海拔自动改为 3.6 km，月度功率全面提升；
6. 依次保存「拉萨」「甘肃」「撒哈拉(23°N, 5°E)」三个场地，右下柱状图直接对比；
7. 点击 ▶ 播放一天 → 整场镜面跟随太阳连续旋转，光晕随 DNI 变化。

## 文件结构

```
web/
  app.py              FastAPI 入口（3 个 API + 静态文件）
  engine_web.py       复用 ../code/engine.py 的包装层（按经纬度/海拔/清澈度参数化 DNI）
  README.md           本文档
  static/
    index.html        单页布局
    css/styles.css    暗色科技感主题
    js/
      scene.js        Three.js 3D 镜场 + 太阳轨迹
      solar.js        JS 端太阳几何（与 Python 公式 1:1）
      map.js          Leaflet 地图
      charts.js       Chart.js 月度曲线 + 场地对比柱
      main.js         总控制器：状态、刷新流水线、事件绑定
```

## API 设计

| 方法 | 路径 | 入参 | 返回 |
|---|---|---|---|
| GET  | `/api/field`   | — | `{positions, width, height, install_height, tower, n}` |
| POST | `/api/instant` | `{lat, lng, altitude_km, clearness, date, time_hours}` | `{sun, dni, efficiencies, power_full_mw, power_render_mw, ppa_kw_m2, per_mirror_eta}` |
| POST | `/api/annual`  | `{lat, lng, altitude_km, clearness}` | `{monthly:[{month,eta,power_mw,dni}], annual:{eta,power_mw,ppa_kw_m2}}` |
| POST | `/api/compare` | `{sites:[AnnualReq, ...]}` | 每个场地的 annual 结果 |

`/api/annual` 以 0.5° 纬度 × 0.5 km 海拔 × 0.05 清澈度的 LRU 缓存，重复调用瞬时返回。

## 物理细节

- **DNI**：按题目附录公式 `G₀(a + b·exp(−c/sinα))`，a/b/c 是海拔的二次回归；额外乘 `clearness` ∈ [0.4, 1.0] 表示大气状况。
- **效率链**：与论文 §3 完全一致——余弦 × 阴影/遮挡 × 大气透射率 × HFLCAL 截断 × 反射率。
- **/api/annual**：为兼顾速度，年度评估在全 3520 面镜上做但跳过阴影/遮挡循环，并用论文中的固定 SHADOW = 0.86 全年平均值补偿；与完整评估的偏差 < 2%。
- **/api/instant**：在 500 面下采样场上做**完整**评估（含 5×5 表面采样的阴影/遮挡），返回每面镜的 η 用于 3D 颜色映射。
