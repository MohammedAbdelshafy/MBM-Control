import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from free_skip_tracer import FreeSkipTracer

tracer = FreeSkipTracer()
result = tracer._search_fastpeoplesearch(address="12602 TRENTON DR, DALLAS, TX, 75243")
print(result)

# Also test DuckDuckGo search for address skip tracing
result_ddg = tracer._search_duckduckgo(name="12602 TRENTON DR", city="DALLAS")
print(result_ddg)
