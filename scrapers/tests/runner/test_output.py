from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from time import sleep

from inflacao_scrapers.execution.output import write_line


class InterruptedStream(StringIO):
    def write(self, value):
        sleep(0.001)
        return StringIO.write(self, value)


def test_simultaneous_diagnostics_remain_complete_lines():
    output = InterruptedStream()
    messages = [f"run_id={index} observations={index}" for index in range(12)]
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda message: write_line(message, file=output), messages))
    assert results == [None] * 12
    text = output.getvalue()
    assert set(text.splitlines()) == set(messages)
    assert len(text.splitlines()) == len(messages)
