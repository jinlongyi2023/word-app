# Notion + Streamlit 背单词 Demo

### 功能
- 从 Notion 数据库拉取单词
- Streamlit 展示交互界面
- Railway 部署上线

### 部署步骤
1. fork 或上传此仓库到 GitHub
2. 在 Railway 新建项目 → 选择此仓库
3. 在 Railway → Variables 添加：
   - NOTION_TOKEN = 你的 Notion Integration Token
   - DATABASE_ID = 你的 Notion 数据库 ID
4. 等待构建完成，访问 Railway 提供的 URL 即可
