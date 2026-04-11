"""
文章质量校验
"""
import re


class ArticleValidator:
    """文章验证器"""

    def __init__(self, min_words=8500, paywall_range=(40, 58)):
        self.min_words = min_words
        self.paywall_range = paywall_range

    def count_words(self, text: str) -> int:
        """统计字数（去除空白后的字符数）"""
        return len(re.sub(r"\s+", "", text))

    def validate(self, article: str) -> dict:
        result = {
            "valid": True,
            "word_count": 0,
            "has_paywall": False,
            "paywall_position": None,
            "issues": [],
        }

        result["word_count"] = self.count_words(article)
        if result["word_count"] < self.min_words:
            result["valid"] = False
            result["issues"].append(f"字数不足：{result['word_count']} < {self.min_words}")

        paywall = self.check_paywall(article)
        result["has_paywall"] = paywall["has_paywall"]
        result["paywall_position"] = paywall["position"]

        if paywall["has_paywall"] and not paywall["valid"]:
            result["issues"].append(
                f"付费墙位置 {paywall['position']:.1f}% 不在 {self.paywall_range[0]}%-{self.paywall_range[1]}% 范围内"
            )

        return result

    def check_paywall(self, article: str) -> dict:
        for pattern in [r"【付费处】", r"\[付费处\]", r"付费点"]:
            match = re.search(pattern, article)
            if match:
                position = (match.start() / len(article)) * 100
                return {
                    "has_paywall": True,
                    "position": round(position, 2),
                    "valid": self.paywall_range[0] <= position <= self.paywall_range[1],
                }
        return {"has_paywall": False, "position": None, "valid": False}

    def insert_paywall(self, article: str, target_position=49) -> str:
        """在指定位置自动插入付费墙"""
        if "【付费处】" in article:
            return article

        target_char = int(len(article) * target_position / 100)
        insert_pos = target_char

        for i in range(min(len(article) - target_char, 500)):
            pos = target_char + i
            if pos >= len(article):
                break
            if article[pos] == "\n" and i > 50:
                insert_pos = pos + 1
                break
            if article[pos] in "。！？":
                insert_pos = pos + 1
                break

        return article[:insert_pos] + "\n\n【付费处】\n\n" + article[insert_pos:]


class TitleValidator:
    @staticmethod
    def validate_title(title: str) -> bool:
        title = title.strip()
        if len(title) < 35 or len(title) > 60:
            return False
        if title.count("，") < 2:
            return False
        return True

    @staticmethod
    def parse_titles(response: str, count=40) -> list:
        """从模型响应中解析标题列表"""
        if "```" in response:
            response = re.sub(r"```[\w]*\n", "", response)
            response = response.replace("```", "")

        titles = []
        for line in response.split("\n"):
            line = line.strip()
            line = re.sub(r"^[\d]+[\s\.、\-—]+", "", line).strip()
            if not line or len(line) < 15:
                continue
            if line.startswith("##") or line.startswith("**") or line.startswith("---"):
                continue
            if line not in titles:
                titles.append(line)
            if len(titles) >= count:
                break

        return titles[:count]
