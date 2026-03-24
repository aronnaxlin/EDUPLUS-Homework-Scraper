# u+平台作业爬取
从在线教育平台 EDUPLUS （u+）爬取课程作业信息，并将其转换为易于阅读和处理的格式

现在推荐使用外置 `JSON` 配置，不需要再把 Cookie 写进代码里。

## 配置文件

先在脚本同目录新建 `config.json`，可直接参考 [`config.json.example`](./config.json.example)：

```json
{
  "session": "你的SESSION",
  "hm_lvt": "",
  "course_id": "你的课程ID"
}
```

说明：
- `hm_lvt` 没有就留空字符串
- `config.json` 已加入 `.gitignore`，避免误提交真实 Cookie

## 运行方式

### eduplus_homework_scraper.py

纯配置文件模式，默认读取脚本同目录下的 `config.json`：

```bash
python3 eduplus_homework_scraper.py
```

### eduplus_homework_scraper_cli.py

配置文件 + 命令行覆盖模式，也会默认读取脚本同目录下的 `config.json`：

```bash
python3 eduplus_homework_scraper_cli.py
```

如果配置文件不在默认位置，可以手动指定：

```bash
python3 eduplus_homework_scraper_cli.py --config /path/to/config.json
```

如果你还想临时覆盖 JSON 里的值，也可以继续传参数：

```bash
python3 eduplus_homework_scraper_cli.py --config /path/to/config.json --session "新的SESSION" --hm_lvt "" --course_id "新的课程ID"
```

## 输出结果

运行后会自动生成：
- `作业题目`：原始 JSON
- `输出结果`：整理后的 TXT
- `输出结果/*_带答案.txt`：带答案版本，会区分 `用户答案`、`正确答案`、`判题结果/得分`（前提是接口返回了这些字段）

course_id 获取方式见：https://www.52pojie.cn/thread-2040508-1-1.html
