# AnyRouter 自动签到脚本

独立版自动签到脚本，支持多账号，支持邮件通知，使用 cron / Windows 任务计划程序定时执行。

## 文件说明

```
anyrouter-checkin/
├── checkin.py          # 签到脚本
├── config.example.json # 配置文件模板
├── README.md           # 说明文档
└── checkin.log         # 签到日志（自动生成）
```

## 快速部署

### 1. 安装依赖

```bash
pip install requests cloudscraper playwright
playwright install chromium
```

> `cloudscraper` 和 `playwright` 用于绕过 Cloudflare 反爬虫挑战。如果不需要，脚本会自动回退到标准 requests。

### 2. 创建配置文件

```bash
cp config.example.json config.json
```

然后编辑 `config.json`，填入你的账号信息和邮件配置：

```json
{
  "base_url": "https://anyrouter.top",
  "accounts": [
    {
      "name": "你的账号名",
      "cookie": "session=你的session值;"
    }
  ],
  "email": {
    "enabled": true,
    "smtp_server": "smtp.qq.com",
    "smtp_port": 465,
    "smtp_user": "你的QQ邮箱地址",
    "smtp_pass": "你的QQ邮箱授权码",
    "recipient": "接收通知的邮箱地址"
  }
}
```

#### 配置说明

| 字段 | 说明 |
|------|------|
| `base_url` | 签到服务地址 |
| `accounts[].name` | 账号备注名，方便在日志中区分 |
| `accounts[].cookie` | 登录后的 session cookie |
| `email.enabled` | 是否启用邮件通知，设为 `false` 可关闭 |
| `email.smtp_*` | 发件邮箱的 SMTP 配置（QQ邮箱默认即可） |
| `email.smtp_pass` | QQ邮箱授权码，不是登录密码！在 QQ邮箱设置 → 账户 → POP3/SMTP 服务中获取 |
| `email.recipient` | 接收签到报告通知的邮箱 |

### 3. 获取 Cookie

1. 打开浏览器，访问 https://anyrouter.top 并登录
2. 按 `F12` 打开开发者工具
3. 切换到 `Application`（应用程序）标签
4. 左侧找到 `Cookies` → `https://anyrouter.top`
5. 找到 `session` 这一行，复制 `Value` 列的值
6. 填入 `config.json` 的 `cookie` 字段，格式为 `session=你复制的值;`

> ⚠️ Cookie 是敏感信息，**不要**将 `config.json` 上传到 GitHub 等公开仓库！

### 4. 手动执行测试

```bash
python checkin.py
```

### 5. 添加定时任务

#### Linux / macOS (cron)

```bash
crontab -e
# 添加以下行（每天早上9点执行）：
0 9 * * * cd /path/to/anyrouter-checkin && python3 checkin.py >> checkin.log 2>&1
```

#### Windows (任务计划程序)

```powershell
# 创建每日任务，9:00 执行
schtasks /create /tn "AnyRouter签到" /tr "D:\tools\python.exe C:\Users\fhkj2\Desktop\anyrouter-checkin\checkin.py" /sc daily /st 09:00
```

## 日志示例

```
2025-04-29 09:00:01 [INFO] ==================================================
2025-04-29 09:00:01 [INFO] AnyRouter 自动签到开始 - 2025-04-29 09:00:01
2025-04-29 09:00:01 [INFO] ==================================================
2025-04-29 09:00:01 [INFO] 共 1 个账号待签到
2025-04-29 09:00:01 [INFO] 签到地址: https://anyrouter.top
2025-04-29 09:00:01 [INFO]
2025-04-29 09:00:01 [INFO] -----> [1/1] 用户名1
2025-04-29 09:00:02 [INFO]   ✅ 签到成功，获得 $25 额度
2025-04-29 09:00:02 [INFO]
2025-04-29 09:00:02 [INFO] ==================================================
2025-04-29 09:00:02 [INFO] 签到完成: 成功 1, 失败 0
2025-04-29 09:00:02 [INFO] ==================================================
```

## 邮件通知

启用后，每次签到完成会自动发送邮件报告，内容包括：

- 签到时间
- 成功/失败汇总
- 每个账号的详细结果

## 常见问题

### 签到失败提示 401？

Cookie 已过期，需要重新获取。登录 https://anyrouter.top 后按上述步骤重新获取 session 值。

### 提示 "Cloudflare 验证" 或请求失败？

脚本会自动尝试使用 Playwright 浏览器处理 JS 挑战。确保已安装：

```bash
playwright install chromium
```

### 不想收到邮件通知？

将 `config.json` 中 `email.enabled` 设为 `false` 即可。

## 注意事项

- `config.json` 包含敏感信息（Cookie、邮箱授权码），**切勿上传到公开仓库**
- Cookie 有效期未知，建议定期检查日志确认签到是否正常
- 如需多账号签到，在 `accounts` 数组中添加多个对象即可