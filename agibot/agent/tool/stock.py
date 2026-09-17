from httpx import AsyncClient


async def stock(num: str):
    """
    根据股票代号查询当前股票行情

    Args:
        num: 股票代号。拼接方式：市场标识 + 股票代码。例如：hk09626 或者 usAAPL
        市场标识如下：sh：上海证券交易所 sz：深圳证券交易所 hk：港股 us：美股。
    """
    async with AsyncClient() as c:
        resp = await c.get(f"https://qt.gtimg.cn/q={num}")
        if resp.status_code >= 400:
            return
        content = resp.content.decode("gbk")
        if '"' not in content:
            return
        content = content.removesuffix('";').strip().split('"')[1]
        fields = content.split("~")
        name = fields[1]
        current = float(fields[3])
        change = float(fields[31])
        change_percent = float(fields[32])
        return f"{name=} 当前{current}点 {change:+.2f} 点，{change_percent:+.2f}%"
