# 在线数据获取 - 快速开始指南

## 修复说明

已修复前端请求超时问题：
- ✅ 增加 API 超时时间（10s → 30s，批量获取 60s）
- ✅ 限制最大页数（20 页上限）
- ✅ 添加用户输入验证和进度提示
- ✅ 优化重试机制（3次 → 2次，避免等待过久）

---

## 使用方法

### 方式 1: Web 界面操作

1. 启动应用：`python app.py`
2. 访问：http://localhost:5000
3. 进入"历史数据"标签
4. 点击"数据管理"
5. 点击"🌐 从福彩网获取"按钮
6. 输入要获取的页数（建议 5-10 页）
7. 等待获取完成

**建议**：
- 首次使用：获取 5 页（约 250 条）
- 定期更新：获取 3 页
- 大量导入：分多次进行，每次不超过 10 页

---

### 方式 2: API 调用

```bash
# 获取最新一期
curl -X POST http://localhost:5000/api/fetch-latest

# 获取 5 页历史数据
curl -X POST http://localhost:5000/api/fetch-history \
  -H "Content-Type: application/json" \
  -d '{"page": 5}'
```

---

### 方式 3: Python 代码

```python
from src.online_fetcher import OnlineFetcher

fetcher = OnlineFetcher()

# 获取单页
result = fetcher.fetch_from_cwl_api(page=1, page_size=50)

# 批量获取
result = fetcher.fetch_multiple_pages(1, 5, use_api=True)

if result['success']:
    print(f"成功获取 {result['total_records']} 条记录")
```

---

## 常见问题

### Q: 为什么不能一次获取所有历史数据？

**A**: 
- 福彩官网有反爬虫机制
- 大量请求会被封 IP
- 建议分批获取，每次 5-10 页

### Q: 获取失败怎么办？

**A**:
1. 减少页数（尝试 3-5 页）
2. 检查网络连接
3. 稍后再试（可能被临时限流）
4. 查看日志文件 `logs/app.log`

### Q: 如何知道获取了多少数据？

**A**: 
- 成功后会显示总记录数
- 在"历史数据"标签查看
- 日志文件中有详细记录

---

## 性能参考

| 页数 | 记录数 | 预计耗时 |
|------|--------|---------|
| 1 页 | ~50 条 | 2-5 秒 |
| 5 页 | ~250 条 | 10-20 秒 |
| 10 页 | ~500 条 | 20-40 秒 |
| 20 页 | ~1000 条 | 40-80 秒 |

---

**更新日期**: 2026-04-29  
**版本**: v1.1 (修复超时问题)
