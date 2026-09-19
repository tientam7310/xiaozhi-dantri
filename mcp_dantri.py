import asyncio
import json
import os
import ssl

import feedparser
import websockets


MCP_URL = os.environ.get("XIAOZHI_MCP_URL")
RSS_URL = "https://dantri.com.vn/rss/home.rss"


def lay_tin_dan_tri():
    feed = feedparser.parse(RSS_URL)

    if not feed.entries:
        raise RuntimeError("Không lấy được RSS Dân Trí.")

    tin = []

    for item in feed.entries[:5]:
        title = item.get("title", "").strip()

        if title:
            tin.append(title)

    if not tin:
        raise RuntimeError("RSS Dân Trí không có tiêu đề.")

    return tin


def tao_noi_dung():
    tin = lay_tin_dan_tri()

    text = "Sau đây là 5 tin mới nhất từ Dân Trí. "

    for i, title in enumerate(tin, 1):
        text += f"Tin thứ {i}: {title}. "

    return text


TOOL = {
    "name": "doc_tin_dan_tri",
    "description": "Đọc 5 tin mới nhất từ báo Dân Trí.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": []
    }
}


def rpc_result(request_id, result):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result
    }


def rpc_error(request_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message
        }
    }


async def xu_ly_message(message):
    try:
        request = json.loads(message)
    except json.JSONDecodeError:
        return None

    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}

    if method == "initialize":
        protocol_version = params.get(
            "protocolVersion",
            "2024-11-05"
        )

        return rpc_result(
            request_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {
                    "tools": {
                        "listChanged": False
                    }
                },
                "serverInfo": {
                    "name": "dantri-mcp",
                    "version": "1.0.0"
                }
            }
        )

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return rpc_result(request_id, {})

    if method == "tools/list":
        return rpc_result(
            request_id,
            {
                "tools": [TOOL]
            }
        )

    if method == "tools/call":
        tool_name = params.get("name")

        if tool_name != "doc_tin_dan_tri":
            return rpc_error(
                request_id,
                -32601,
                f"Không tìm thấy tool: {tool_name}"
            )

        try:
            print("Đang lấy tin Dân Trí...")

            text = tao_noi_dung()

            print(text)

            return rpc_result(
                request_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": text
                        }
                    ],
                    "isError": False
                }
            )

        except Exception as e:
            return rpc_result(
                request_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Lỗi khi lấy tin Dân Trí: {e}"
                        }
                    ],
                    "isError": True
                }
            )

    if request_id is not None:
        return rpc_error(
            request_id,
            -32601,
            f"Method không được hỗ trợ: {method}"
        )

    return None


async def ket_noi_mcp():

    if not MCP_URL:
        print("Thiếu biến XIAOZHI_MCP_URL.")
        return

    print("======================================")
    print(" MCP DÂN TRÍ CHO XIAOZHI")
    print("======================================")
    print("Đang kết nối MCP Endpoint...")

    ssl_context = ssl.create_default_context()

    async with websockets.connect(
        MCP_URL,
        ssl=ssl_context,
        ping_interval=20,
        ping_timeout=20,
        max_size=2 * 1024 * 1024
    ) as websocket:

        print("Đã kết nối MCP Endpoint.")
        print("Đang chờ Xiaozhi gọi tool...")

        async for message in websocket:

            response = await xu_ly_message(message)

            if response is not None:

                response_text = json.dumps(
                    response,
                    ensure_ascii=False
                )

                await websocket.send(response_text)


async def main():

    while True:

        try:
            await ket_noi_mcp()

        except KeyboardInterrupt:
            print("Đã dừng.")
            break

        except Exception as e:

            print("Mất kết nối hoặc có lỗi:")
            print(e)

            print("Thử kết nối lại sau 5 giây...")

            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
