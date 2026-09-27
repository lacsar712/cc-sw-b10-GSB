# 光谱波长校准台

校准员提交标称波长与实测波长。独立领取进程按允差写出合格或超差。页面轮询直到结论出现。

顶栏「轨迹台」专页按时间倒序列出近次已结案轨迹点（标称/实测/偏差/结论），条数可选；点击某行设为对照点后，由服务端计算各点对该点的实测差额与偏差差额。校准员可签发轨迹副本，签发即冻结当时的点集与差额；之后新结论只影响在线轨迹，历史副本不变。校准员与检验员都可查看轨迹与副本，仅校准员可签发。

## 端口

| 服务 | 地址 |
|------|------|
| 页面 | http://localhost:3195 |
| 接口 | http://localhost:8195 |
| PostgreSQL | localhost:54395 |

## 账号

| 用户 | 密码 | 权限 |
|------|------|------|
| calibrator | calib123456 | 可提交校准、可签发轨迹副本 |
| inspector | insp123456 | 只看 |

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/trajectory?limit=N&compare_id=M | 近 N 条已结案轨迹点；带 compare_id 时服务端算各点差额 |
| POST | /api/trajectory/snapshots | 签发轨迹副本（仅校准员），冻结当前点集与差额 |
| GET | /api/trajectory/snapshots | 已签发快照列表 |
| GET | /api/trajectory/snapshots/{id} | 快照副本详情（冻结数据） |

## 启动

```bash
cd projects/16-spectrum-wavelength-desk
docker compose up --build
```

## 验收

1. calibrator 登录后，种子「氦灯-587」合格、「汞灯-546」超差。
2. 再提交超差样条，先待处理再出超差。
3. inspector 不能提交。
4. 顶栏进「轨迹台」，按时间列出近次已结案点并标合格/超差，条数可切换。
5. 点击某行设为对照点，差额区与表内差额列由服务端算出。
6. calibrator 签发轨迹副本后继续提交新笔；再打开该副本，点集与差额仍停在签发版。
7. inspector 能看轨迹与副本，但无签发入口，直接调签发接口返回 403。
