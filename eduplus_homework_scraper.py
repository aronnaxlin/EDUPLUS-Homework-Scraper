import requests
import json
from datetime import datetime
import time
import re
import os
import glob
from html import unescape

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
HM_LVT_COOKIE_NAME = "Hm_lvt_bc32be924d31063c4e643e095e69926a"
COURSE_ID = ""

# 配置headers和cookies
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36',
    'Referer': 'https://www.eduplus.net/student/courses',
    'Accept': 'application/json, text/plain, */*',
}

COOKIES = {
    'SESSION': '',
    HM_LVT_COOKIE_NAME: '',
}


def mask_value(value, visible=6):
    """隐藏敏感配置，只显示首尾少量字符"""
    if not value:
        return "(空)"
    if len(value) <= visible * 2:
        return value
    return f"{value[:visible]}...{value[-visible:]}"


def load_config(config_path=CONFIG_PATH):
    """从外置JSON加载运行配置"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"配置文件不存在: {config_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"配置文件JSON格式错误: {e}")
        return None

    if not isinstance(config, dict):
        print("配置文件格式错误: 根节点必须是JSON对象")
        return None

    raw_cookies = config.get("cookies", {})
    cookies = raw_cookies if isinstance(raw_cookies, dict) else {}

    session_cookie = str(config.get("session", cookies.get("SESSION", "")) or "")
    hm_lvt_cookie = str(config.get("hm_lvt", cookies.get(HM_LVT_COOKIE_NAME, "")) or "")
    course_id = str(config.get("course_id", "") or "")

    if not session_cookie:
        print("配置文件缺少必要字段: session")
        return None

    if not course_id:
        print("配置文件缺少必要字段: course_id")
        return None

    return {
        "session": session_cookie,
        "hm_lvt": hm_lvt_cookie,
        "course_id": course_id,
        "config_path": config_path,
    }


def safe_filename(filename):
    """创建安全的文件名"""
    return re.sub(r'[\\/*?:"<>|]', '', filename)


def clean_html(text):
    """清理HTML标签和实体"""
    if text is None:
        return ""
    text = unescape(text)  # 转换HTML实体
    text = re.sub(r'<[^>]+>', '', text)  # 移除HTML标签
    text = re.sub(r'\s+', ' ', text)  # 合并多余空格
    return text.strip()


def get_homework_list(course_id):
    """获取课程作业列表"""
    url = f"https://www.eduplus.net/api/course/homeworks/published/student?courseId={course_id}"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            cookies=COOKIES,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()

        if not data.get('success') or 'data' not in data:
            print("错误：API响应无效")
            return []

        homework_items = []
        for item in data['data']:
            homework = item.get('homeworkDTO', {})
            if 'id' in homework and 'name' in homework:
                homework_items.append({
                    'sequence': item.get('sequence', 0),
                    'name': homework['name'],
                    'id': homework['id']
                })

        homework_items.sort(key=lambda x: x['sequence'])
        result = [{'name': item['name'], 'id': item['id']} for item in homework_items]
        return result

    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
    except json.JSONDecodeError:
        print("错误：响应不是有效的JSON格式")
    except Exception as e:
        print(f"处理数据时出错: {e}")

    return []


def get_question_detail(question_id):
    """获取单个题目的详细内容"""
    detail_api = f"https://www.eduplus.net/api/course/homeworkQuestions/{question_id}/student/detail"

    try:
        response = requests.get(
            detail_api,
            headers=HEADERS,
            cookies=COOKIES,
            timeout=15
        )
        response.raise_for_status()

        if response.status_code != 200:
            print(f"获取题目详情失败: HTTP {response.status_code}")
            return None

        data = response.json()
        if data.get('code') not in [2000000, "OK"]:
            print(f"题目详情API错误: {data.get('message')}")
            return None

        return data.get('data')

    except requests.exceptions.RequestException as e:
        print(f"网络请求异常: {e}")
        return None


def get_sorted_questions(homework_id):
    """获取作业的题目并按orderNumber排序"""
    questions_api = f"https://www.eduplus.net/api/course/homeworkQuestions/student?homeworkId={homework_id}"

    try:
        response = requests.get(
            questions_api,
            headers=HEADERS,
            cookies=COOKIES,
            timeout=15
        )
        response.raise_for_status()

        if response.status_code != 200:
            print(f"获取题目失败: HTTP {response.status_code}")
            return []

        data = response.json()
        if data.get('code') not in [2000000, "OK"]:
            print(f"API错误: {data.get('message')}")
            return []

        questions = data.get('data', [])
        sorted_questions = sorted(
            questions,
            key=lambda q: int(q.get('orderNumber', 99999))
        )  # 默认值确保未编号的在最后

        detailed_questions = []
        for i, question in enumerate(sorted_questions):
            question_id = question.get('id')
            if not question_id:
                continue

            detail = get_question_detail(question_id)
            if detail:
                question['detail'] = detail
                detailed_questions.append(question)

            time.sleep(0.3)  # 避免请求过快

        return detailed_questions

    except requests.exceptions.RequestException as e:
        print(f"网络请求异常: {e}")
        return []
    except (TypeError, ValueError) as e:
        print(f"数据处理错误: {e}")
        return []


def process_homework(homework, output_dir):
    """处理单个作业并保存结果"""
    try:
        homework_name = homework["name"]
        homework_id = homework["id"]
        safe_name = safe_filename(homework_name)

        questions = get_sorted_questions(homework_id)
        if not questions:
            print(f"未能获取到作业 '{homework_name}' 的任何题目")
            return None

        # 创建JSON文件路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"作业_{safe_name}_{timestamp}.json"
        json_path = os.path.join(output_dir, json_filename)

        # 保存JSON数据
        with open(json_path, 'w', encoding='utf-8') as f:
            json_data = {
                "homework_name": homework_name,
                "homework_id": homework_id,
                "timestamp": datetime.now().isoformat(),
                "question_count": len(questions),
                "questions": questions
            }
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        return json_path

    except KeyError as e:
        print(f"配置错误: 作业字典缺少必要的键 {e}")
    except Exception as e:
        print(f"处理作业时发生未知错误: {str(e)}")

    return None


def split_answer_tokens(answer):
    """将答案字符串拆分为可展示的标记列表"""
    if answer is None:
        return []

    if isinstance(answer, list):
        return [str(item).strip() for item in answer if str(item).strip()]

    answer_text = str(answer).strip()
    if not answer_text:
        return []

    if ',' in answer_text:
        return [token.strip() for token in answer_text.split(',') if token.strip()]

    if re.fullmatch(r'[A-Za-z]+', answer_text):
        return list(answer_text.upper())

    return [answer_text]


def format_answer_value(detail, answer_value):
    """根据题型格式化答案文本"""
    if answer_value in (None, ""):
        return "(未提供)"

    qsn_type = detail.get('qsnType')
    if qsn_type == 3:
        mapping = {
            'true': '正确',
            'false': '错误',
        }
        return mapping.get(str(answer_value).strip().lower(), str(answer_value))

    if qsn_type in [1, 2]:
        option_map = {}
        for opt in detail.get('options', []):
            option_id = str(opt.get('id', '')).strip().upper()
            option_content = clean_html(opt.get('optionContent', ''))
            if option_id:
                option_map[option_id] = option_content

        formatted_options = []
        for token in split_answer_tokens(answer_value):
            option_id = token.upper()
            option_content = option_map.get(option_id)
            if option_content:
                formatted_options.append(f"{option_id}. {option_content}")
            else:
                formatted_options.append(token)

        return "；".join(formatted_options) if formatted_options else str(answer_value)

    if qsn_type == 6:
        tokens = split_answer_tokens(answer_value)
        return "；".join(tokens) if tokens else str(answer_value)

    return str(answer_value)


def get_question_type_label(qsn_type):
    """返回题型中文标签"""
    mapping = {
        1: '单选题',
        2: '多选题',
        3: '判断题',
        6: '填空题',
    }
    return mapping.get(qsn_type)


def write_text_output(data, text_path, include_answers=False):
    """将JSON题目数据写入文本文件"""
    with open(text_path, 'w', encoding='utf-8') as out_f:
        homework_name = data.get('homework_name', '未知作业')
        out_f.write(f"作业名称: {homework_name}\n")
        out_f.write(f"题目数量: {data.get('question_count', 0)}\n")
        out_f.write(f"导出时间: {data.get('timestamp', '')}\n")
        if include_answers:
            out_f.write("导出类型: 带答案版本\n")
        out_f.write("=" * 60 + "\n\n")

        for idx, question in enumerate(data.get('questions', [])):
            detail = question.get('detail', {})
            qsn_type = detail.get('qsnType')
            title = clean_html(detail.get('titleText', ''))
            question_num = idx + 1
            question_type_label = get_question_type_label(qsn_type)

            out_f.write(f"题目 {question_num}: {title}\n")
            if question_type_label:
                out_f.write(f"  ({question_type_label})\n")

            if qsn_type in [1, 2]:
                options = detail.get('options', [])
                for opt_idx, opt in enumerate(options):
                    content = clean_html(opt.get('optionContent', ''))
                    out_f.write(f"  {chr(65 + opt_idx)}. {content}\n")

            elif qsn_type not in [3, 6]:
                out_f.write(f"  (未知题型: {qsn_type})\n")

            if include_answers:
                user_answer = detail.get('userAnswer')
                if user_answer not in (None, ""):
                    out_f.write(f"  用户答案: {format_answer_value(detail, user_answer)}\n")
                else:
                    out_f.write("  用户答案: (未作答)\n")

                correct_answer = detail.get('answer')
                if correct_answer not in (None, ""):
                    out_f.write(f"  正确答案: {format_answer_value(detail, correct_answer)}\n")

                if 'isCorrect' in detail:
                    out_f.write(f"  判题结果: {'正确' if detail.get('isCorrect') == 1 else '错误'}\n")

                score = detail.get('userScore', question.get('userScore'))
                if score is not None:
                    out_f.write(f"  得分: {score}\n")

            out_f.write("\n")


def convert_to_text(json_path, output_dir):
    """将JSON文件转换为文本格式"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        base_name = os.path.splitext(os.path.basename(json_path))[0]
        plain_output_dir = os.path.join(output_dir, "不带答案")
        answer_output_dir = os.path.join(output_dir, "带答案")
        os.makedirs(plain_output_dir, exist_ok=True)
        os.makedirs(answer_output_dir, exist_ok=True)

        text_filename = f"{base_name}.txt"
        text_path = os.path.join(plain_output_dir, text_filename)
        answer_text_filename = f"{base_name}_带答案.txt"
        answer_text_path = os.path.join(answer_output_dir, answer_text_filename)

        write_text_output(data, text_path, include_answers=False)
        write_text_output(data, answer_text_path, include_answers=True)

        print(f"已创建文本文件: {text_path}")
        print(f"已创建带答案文本文件: {answer_text_path}")

        return text_path

    except Exception as e:
        print(f"转换文件 {json_path} 时出错: {str(e)}")
        return None


def main():
    config = load_config()
    if not config:
        return

    global COURSE_ID, COOKIES
    COURSE_ID = config["course_id"]
    COOKIES = {
        'SESSION': config["session"],
        HM_LVT_COOKIE_NAME: config["hm_lvt"],
    }

    # 创建目录结构
    base_dir = os.getcwd()
    json_dir = os.path.join(base_dir, "作业题目")
    text_dir = os.path.join(base_dir, "输出结果")

    os.makedirs(json_dir, exist_ok=True)
    os.makedirs(text_dir, exist_ok=True)

    print("=" * 60)
    print("EDUPLUS 作业题目爬取与转换工具")
    print("=" * 60)
    print(f"配置文件: {config['config_path']}")
    print(f"课程ID: {COURSE_ID}")
    print(f"SESSION Cookie: {mask_value(config['session'])}")
    print(f"Hm_lvt Cookie: {mask_value(config['hm_lvt'])}")

    # 第一步：获取作业列表
    homeworks = get_homework_list(COURSE_ID)
    if not homeworks:
        print("未获取到任何作业，请检查配置和网络连接")
        return

    print(f"找到 {len(homeworks)} 个作业")

    # 第二步：处理每个作业
    json_files = []
    for homework in homeworks:
        print(f"\n处理作业: {homework['name']}")
        json_path = process_homework(homework, json_dir)
        if json_path:
            json_files.append(json_path)
            print(f"已保存JSON文件: {json_path}")
        time.sleep(1)  # 作业间间隔

    # 第三步：转换JSON为文本
    print("\n开始转换JSON文件为文本格式...")
    for json_file in json_files:
        convert_to_text(json_file, text_dir)

    # 第四步：处理之前下载的JSON文件（如果有）
    existing_files = glob.glob(os.path.join(json_dir, '*.json'))
    for json_file in existing_files:
        if json_file not in json_files:
            print(f"处理之前下载的文件: {os.path.basename(json_file)}")
            convert_to_text(json_file, text_dir)

    print("\n" + "=" * 60)
    print(f"所有处理完成! 共处理 {len(json_files)} 个作业")
    print(f"JSON文件目录: {json_dir}")
    print(f"文本文件目录: {text_dir}")
    print(f"不带答案文本目录: {os.path.join(text_dir, '不带答案')}")
    print(f"带答案文本目录: {os.path.join(text_dir, '带答案')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
