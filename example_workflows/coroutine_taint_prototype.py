import asyncio
from aco.runner.taint_wrappers import TaintStr

async def process_data(data: str) -> str:
    """User function that should propagate taint through string operations"""
    assert isinstance(data, TaintStr), "data is not tainted"
    return await asyncio.sleep(0.5)

async def test_taint_preservation():
    tainted_input = TaintStr("secret", taint_origin=["user_input"])
    print("Calling asyncio.wait_for with user coroutine...")
    await asyncio.wait_for(process_data(tainted_input), timeout=5.0)

if __name__ == "__main__":
    asyncio.run(test_taint_preservation())