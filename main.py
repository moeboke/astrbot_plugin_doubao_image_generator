import os
import aiohttp
from openai import OpenAI
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import At, Image, Plain
from astrbot.api import logger

# 初始化 OpenAI 客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key="",  # 请确保替换为正确的 API Key
)

# 错误码与含义映射表
ERROR_MEANINGS = {
    "MissingParameter": "请求缺少必要参数，请查阅 API 文档。",
    "InvalidParameter": "请求包含非法参数，请查阅 API 文档。",
    "InvalidEndpoint.ClosedEndpoint": "推理接入点处于已被关闭或暂时不可用，请稍后重试，或联系推理接入点管理员。",
    "SensitiveContentDetected": "输入文本可能包含敏感信息，请您使用其他 prompt。",
    "SensitiveContentDetected.SevereViolation": "输入文本可能包含严重违规相关信息，请您使用其他 prompt。",
    "SensitiveContentDetected.Violence": "输入文本可能包含激进行为相关信息，请您使用其他 prompt。",
    "InputTextSensitiveContentDetected": "输入文本可能包含敏感信息，请您更换后重试。",
    "InputImageSensitiveContentDetected": "输入图像可能包含敏感信息，请您更换后重试。",
    "OutputVideoSensitiveContentDetected": "生成的视频可能包含敏感信息，请您更换输入内容后重试。",
    "AuthenticationError": "请求携带的 API Key 或 AK/SK 校验未通过，请您重新检查设置的鉴权凭证，或者查看 API 调用文档来排查问题。",
    "RateLimitExceeded.EndpointRPMExceeded": "请求所关联的推理接入点已超过 RPM (Requests Per Minute) 限制，请稍后重试。",
    "RateLimitExceeded.EndpointTPMExceeded": "请求所关联的推理接入点已超过 TPM (Tokens Per Minute) 限制，请稍后重试。",
    "InternalServiceError": "内部系统异常，请您稍后重试。",
    "InternalError": "未知错误，请稍后重试。如果多次尝试仍失败，请提交工单。",
    "OutputImageSensitiveContentDetected": " 请求失败，因为输出图像可能包含敏感信息",
   
    # 添加其他错误码和含义...
}

def parse_error(error: dict) -> str:
    """解析错误信息并返回对应含义"""
    error_code = error.get("code", "UnknownError")
    error_message = error.get("message", "未知错误")
    request_id = error.get("request_id", "无")
    meaning = ERROR_MEANINGS.get(error_code, "未知错误，请稍后重试。")
    return (
        f"HTTP 状态码: 400\n"
        f"错误类型: {error.get('type', 'UnknownType')}\n"
        f"错误码: {error_code}\n"
        f"错误信息: {error_message}\n"
        f"含义: {meaning}"
    )

@register(
    "astrbot_plugin_doubao_image_generator",
    "moeboke",
    "AI画图插件",
    "1.0.0",
    "https://github.com/your-repo/astrbot_plugin_doubao_image_generator"
)
class ImageGeneratorPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("画图", alias={'生成图片', 'ai画图', '绘图'})
    async def generate_image(self, event: AstrMessageEvent):
        '''AI画图功能\n用法：/画图 prompt'''
        args = event.message_str.split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("请输入画图的描述，例如：/画图 一只可爱的猫咪坐在草地上。")
            return

        prompt = args[1]
        sender_id = event.get_sender_id()

        try:
            response = client.images.generate(
                model="doubao-seedream-3-0-t2i-250415",
                prompt=prompt,
                size="1024x1024",
                response_format="url"
            )
            image_url = response.data[0].url

            # 下载图片到本地
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status != 200:
                        raise Exception(f"图片下载失败，状态码：{resp.status}")
                    image_data = await resp.read()
                    image_path = os.path.join(os.path.dirname(__file__), "temp_image.png")
                    with open(image_path, "wb") as f:
                        f.write(image_data)

            # 构造消息链
            message_chain = [
                At(qq=sender_id),
                Plain(f"根据您的描述生成的图片如下："),
                Image.fromFileSystem(image_path)
            ]

            # 发送消息
            yield event.chain_result(message_chain)

            # 删除临时图片文件
            os.remove(image_path)

        except Exception as e:
            error_message = str(e)
            try:
                # 尝试解析 API 返回的错误信息
                error_data = eval(error_message.split(" - ")[-1])  # 提取 JSON 数据
                error_output = parse_error(error_data.get("error", {}))
                yield event.plain_result(error_output)
            except Exception:
                logger.error(f"生成图片失败: {error_message}", exc_info=True)
                yield event.plain_result("生成图片失败，请稍后再试或检查描述是否过于复杂。")

    async def terminate(self):
        '''清理资源'''
        pass
