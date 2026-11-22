from langchain_core.messages import AIMessage, SystemMessage

from vendor_review.models import LocalCall, LocalDecision, StructuredLocalModel
from vendor_review.schemas import tool_schemas


def test_local_structured_decision_becomes_tool_request_with_usage():
    class LocalFixture:
        def with_structured_output(self, schema, method, include_raw):
            assert schema is LocalDecision and method == "json_schema" and include_raw
            return self

        def invoke(self, messages):
            assert "Tool contracts:" in messages[0].content
            return {
                "parsed": LocalDecision(
                    reply="",
                    calls=[
                        LocalCall(name="identify_company", arguments={"identifier": "example.com"})
                    ],
                ),
                "raw": AIMessage(
                    content="fixture",
                    usage_metadata={"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
                ),
            }

    model = StructuredLocalModel(LocalFixture()).bind_tools(tool_schemas())
    response = model.invoke([SystemMessage(content="instructions")])
    assert response.tool_calls[0]["name"] == "identify_company"
    assert response.tool_calls[0]["args"] == {"identifier": "example.com"}
    assert response.usage_metadata["total_tokens"] == 30
