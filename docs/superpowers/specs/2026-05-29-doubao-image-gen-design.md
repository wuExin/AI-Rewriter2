# 豆包生图功能设计

## 目标

在 RewritePipeline（元宝改写）流程中，增加豆包生图步骤，根据原文标题自动生成一张封面图片，与改写文章保存在同一目录。

## 适用范围

仅 **RewritePipeline**（抓取→分析→改写→标题→生图→保存）。

## 变更后流程

```
抓取原文 → 分析文章 → 改写文章 → 生成标题 → 豆包生图 → 保存文件
```

生图在标题生成后、保存前执行。生图失败不影响整体流程，仅记录 warning 日志。

## 新增文件

### `src/image_gen.py`

`DoubaoImageGenerator` 类，封装豆包网页版生图完整逻辑。

```python
class DoubaoImageGenerator:
    def __init__(self, output_dir: str, chromedriver_dir: str):
        """
        Args:
            output_dir: 图片输出目录
            chromedriver_dir: chromedriver 所在目录（含 chromedriver.exe 和 user_data/）
        """

    def generate(self, title: str, filename: str = None) -> str | None:
        """
        根据标题生成一张封面图片。

        Args:
            title: 原文标题
            filename: 输出文件名（不含路径），默认 {safe_title}_封面.png

        Returns:
            图片文件路径，失败返回 None
        """
        prompt = (
            f"根据下面标题，要求只生成一张照片，要求符合标题大意，"
            f"影视化场景，亚洲人，照片中不要出现文字，尺寸1200*800\n"
            f"标题：【{title}】"
        )
        # 1. 启动 Chrome（持久化 user_data）
        # 2. 打开豆包 https://www.doubao.com/chat/
        # 3. 注入去水印 JS（劫持 JSON.parse，替换 image_ori.url 为 image_ori_raw.url）
        # 4. 发送 prompt 到 textarea
        # 5. 等待图片生成（最长 timeout 秒）
        # 6. 下载无水印图片到 output_dir
        # 7. 关闭浏览器
```

实现细节参考 `F:\private\步里软件【编号2544】豆包文章自动配图工具\simple_generate.py`：
- Selenium + Chrome 浏览器自动化
- 持久化 `user_data` 目录保存登录状态
- JS 注入去水印脚本
- 通过 `flow-imagex` URL 匹配定位生成的图片
- `requests` 携带浏览器 Cookie 下载无水印原图

## 对 RewritePipeline 的改动

`src/pipeline.py` 中 `RewritePipeline.run()` 方法：

1. 导入 `DoubaoImageGenerator`
2. 标题生成之后、保存之前，新增生图步骤：
   ```python
   image_path = None
   if self.config.get("image_gen", {}).get("enabled", False):
       self._log("[5/5] 正在生成封面图...", "info")
       try:
           gen = DoubaoImageGenerator(
               output_dir=self.output_dir,
               chromedriver_dir=self.config["image_gen"]["chromedriver_dir"],
           )
           image_path = gen.generate(title)
           if image_path:
               self._log(f"[OK] 封面图已保存: {image_path}", "success")
           else:
               self._log("[WARN] 封面图生成失败，跳过", "warning")
       except Exception as e:
           self._log(f"[WARN] 封面图生成异常: {e}", "warning")
   ```
3. `result` 字典新增 `"image_path"` 字段

## 配置

`config.yaml` 新增：

```yaml
image_gen:
  enabled: true
  chromedriver_dir: "./chromedriver"
  timeout: 120
```

## 文件输出

图片和文章放在同一 `output` 目录下，命名规则：

| 文件 | 命名 |
|------|------|
| 改写文章 | `{safe_title}_改写.docx` |
| 封面图片 | `{safe_title}_封面.png` |

## 错误处理

- 豆包未登录：首次运行需用户手动登录，持久化 Cookie 后后续自动登录
- 生图超时：返回 None，warning 日志，不影响文章保存
- ChromeDriver 缺失：启动时报错，warning 日志，不影响文章保存
- 浏览器异常：finally 块确保 `driver.quit()`
