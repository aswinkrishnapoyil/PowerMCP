import builtins
import json
import sys
import unittest
from types import ModuleType


class FakeFastMCP:
    def __init__(self, *args, **kwargs):
        pass

    def tool(self):
        return lambda function: function


mcp = ModuleType("mcp")
mcp_server = ModuleType("mcp.server")
mcpserver = ModuleType("mcp.server.mcpserver")
mcpserver.MCPServer = FakeFastMCP
sys.modules["mcp"] = mcp
sys.modules["mcp.server"] = mcp_server
sys.modules["mcp.server.mcpserver"] = mcpserver

powermcp_sandbox = ModuleType("powermcp.sandbox")
powermcp_sandbox.checked_path = lambda path, **kwargs: path
powermcp_sandbox.checked_read_tree = lambda *args, **kwargs: []
powermcp_sandbox.ensure_checked_directory = lambda path, **kwargs: path
sys.modules["powermcp.sandbox"] = powermcp_sandbox


class FakeAgent:
    _shared_app = None


agent_module = ModuleType("Agent_DIgSILENT")
agent_module.SimulationConfig = object
agent_module.DIgSILENTAgent = FakeAgent
sys.modules["Agent_DIgSILENT"] = agent_module

original_print = builtins.print
import MCP_PowerFactory as mcp_module
builtins.print = original_print

mcp_module._pf = lambda function, *args, **kwargs: function(*args, **kwargs)


class FakeObject:
    def __init__(
        self,
        name,
        class_name,
        full_name,
        attributes=None,
        contents=None,
        parent=None,
    ):
        self.class_name = class_name
        self.full_name = full_name
        self.attributes = {"loc_name": name}
        self.attributes.update(attributes or {})
        self.contents = contents or {}
        self.parent = parent

    def GetAttribute(self, attribute):
        return self.attributes[attribute]

    def GetClassName(self):
        return self.class_name

    def GetFullName(self):
        return self.full_name

    def GetParent(self):
        return self.parent

    def GetContents(self, pattern, recursive):
        return self.contents.get(pattern, [])


class FakeFolder:
    def __init__(self, contents):
        self.contents = contents

    def GetContents(self, pattern, recursive):
        return self.contents


class FakeApplication:
    def __init__(self, project, active_case, study_cases, objects):
        self.project = project
        self.active_case = active_case
        self.study_folder = FakeFolder(study_cases)
        self.objects = objects

    def GetActiveProject(self):
        return self.project

    def GetActiveStudyCase(self):
        return self.active_case

    def GetCalcRelevantObjects(self, query):
        return self.objects.get(query, [])

    def GetProjectFolder(self, folder_name):
        return self.study_folder if folder_name == "study" else None


class StateInspectionTest(unittest.TestCase):
    def test_get_network_topology(self):
        project = FakeObject("test", "IntPrj", r"\user\test.IntPrj")
        study_case = FakeObject(
            "Case 1",
            "IntCase",
            r"\user\test.IntPrj\Study Cases\Case 1.IntCase",
        )
        bus_1 = FakeObject(
            "Bus 01",
            "ElmTerm",
            r"\user\test.IntPrj\Grid\Bus 01.ElmTerm",
            {"outserv": 0, "uknom": 345.0},
        )
        bus_2 = FakeObject(
            "Bus 02",
            "ElmTerm",
            r"\user\test.IntPrj\Grid\Bus 02.ElmTerm",
            {"outserv": 0, "uknom": 345.0},
        )
        bus_3 = FakeObject(
            "Bus 03",
            "ElmTerm",
            r"\user\test.IntPrj\Grid\Bus 03.ElmTerm",
            {"outserv": 1, "uknom": 110.0},
        )

        closed_switch = FakeObject(
            "Switch",
            "StaSwitch",
            r"\user\test.IntPrj\Grid\Bus 01\Line Cubi\Switch.StaSwitch",
            {"on_off": 1},
        )
        open_switch = FakeObject(
            "Switch",
            "StaSwitch",
            r"\user\test.IntPrj\Grid\Bus 02\Trf Cubi\Switch.StaSwitch",
            {"on_off": 0},
        )
        line_cubicle_1 = FakeObject(
            "Line Cubi",
            "StaCubic",
            r"\user\test.IntPrj\Grid\Bus 01\Line Cubi.StaCubic",
            contents={"*.StaSwitch": [closed_switch]},
            parent=bus_1,
        )
        line_cubicle_2 = FakeObject(
            "Line Cubi",
            "StaCubic",
            r"\user\test.IntPrj\Grid\Bus 02\Line Cubi.StaCubic",
            parent=bus_2,
        )
        transformer_cubicle_1 = FakeObject(
            "Trf Cubi",
            "StaCubic",
            r"\user\test.IntPrj\Grid\Bus 02\Trf Cubi.StaCubic",
            contents={"*.StaSwitch": [open_switch]},
            parent=bus_2,
        )
        transformer_cubicle_2 = FakeObject(
            "Trf Cubi",
            "StaCubic",
            r"\user\test.IntPrj\Grid\Bus 03\Trf Cubi.StaCubic",
            parent=bus_3,
        )
        line = FakeObject(
            "Line 01 - 02",
            "ElmLne",
            r"\user\test.IntPrj\Grid\Line 01 - 02.ElmLne",
            {
                "bus1": line_cubicle_1,
                "bus2": line_cubicle_2,
                "outserv": 0,
            },
        )
        transformer = FakeObject(
            "Trf 02 - 03",
            "ElmTr2",
            r"\user\test.IntPrj\Grid\Trf 02 - 03.ElmTr2",
            {
                "bushv": transformer_cubicle_1,
                "buslv": transformer_cubicle_2,
                "outserv": 0,
            },
        )
        coupler = FakeObject(
            "Open Coupler",
            "ElmCoup",
            r"\user\test.IntPrj\Grid\Open Coupler.ElmCoup",
            {
                "bus1": line_cubicle_1,
                "bus2": line_cubicle_2,
                "outserv": 0,
                "on_off": 0,
            },
        )
        unresolved = FakeObject(
            "Broken Line",
            "ElmLne",
            r"\user\test.IntPrj\Grid\Broken Line.ElmLne",
            {"bus1": line_cubicle_1, "bus2": None, "outserv": 0},
        )
        grid = FakeObject(
            "Grid",
            "ElmNet",
            r"\user\test.IntPrj\Grid.ElmNet",
            contents={
                "*.ElmTerm": [bus_1, bus_2, bus_3],
                "*.ElmLne": [line, unresolved],
                "*.ElmTr2": [transformer],
                "*.ElmCoup": [coupler],
            },
        )

        FakeAgent._shared_app = FakeApplication(
            project=project,
            active_case=study_case,
            study_cases=[study_case],
            objects={"*.ElmNet": [grid]},
        )
        FakeAgent._select_grid = staticmethod(
            lambda app, grid_name: app.GetCalcRelevantObjects("*.ElmNet")[0]
        )

        topology = json.loads(
            mcp_module.get_network_topology(
                "Grid",
                in_service_only=True,
                include_adjacency=True,
            )
        )

        self.assertTrue(topology["success"])
        self.assertEqual(topology["node_count"], 2)
        self.assertEqual(topology["edge_count"], 1)
        self.assertEqual(topology["edges"][0]["kind"], "line")
        self.assertTrue(topology["edges"][0]["in_service"])
        self.assertEqual(len(topology["unresolved_edges"]), 1)
        self.assertEqual(
            topology["adjacency"][bus_1.GetFullName()],
            [bus_2.GetFullName()],
        )
        self.assertEqual(
            topology["adjacency"][bus_2.GetFullName()],
            [bus_1.GetFullName()],
        )

        complete = json.loads(
            mcp_module.get_network_topology(
                "Grid",
                in_service_only=False,
            )
        )
        self.assertEqual(complete["node_count"], 3)
        self.assertEqual(complete["edge_count"], 3)
        transformer_edge = next(
            edge
            for edge in complete["edges"]
            if edge["kind"] == "transformer"
        )
        self.assertFalse(transformer_edge["in_service"])
        coupler_edge = next(
            edge
            for edge in complete["edges"]
            if edge["kind"] == "coupler"
        )
        self.assertFalse(coupler_edge["in_service"])

    def test_get_network_info(self):
        project = FakeObject(
            "test",
            "IntPrj",
            r"\user\test.IntPrj",
        )
        study_case = FakeObject(
            "Case 1",
            "IntCase",
            r"\user\test.IntPrj\Study Cases\Case 1.IntCase",
        )
        bus_1 = FakeObject(
            "Bus 01",
            "ElmTerm",
            r"\user\test.IntPrj\Grid\Bus 01.ElmTerm",
            {"outserv": 0, "uknom": 345.0},
        )
        bus_2 = FakeObject(
            "Bus 02",
            "ElmTerm",
            r"\user\test.IntPrj\Grid\Bus 02.ElmTerm",
            {"outserv": 1, "uknom": 110.0},
        )
        line = FakeObject(
            "Line 01 - 02",
            "ElmLne",
            r"\user\test.IntPrj\Grid\Line 01 - 02.ElmLne",
            {"outserv": 0},
        )
        breaker = FakeObject(
            "Switch",
            "StaSwitch",
            r"\user\test.IntPrj\Grid\Bus 01\Cubi\Switch.StaSwitch",
            {"on_off": 1},
        )
        grid = FakeObject(
            "Grid",
            "ElmNet",
            r"\user\test.IntPrj\Grid.ElmNet",
            contents={
                "*.ElmTerm": [bus_1, bus_2],
                "*.ElmLne": [line],
                "*.StaSwitch": [breaker],
            },
        )

        FakeAgent._shared_app = FakeApplication(
            project=project,
            active_case=study_case,
            study_cases=[study_case],
            objects={"*.ElmNet": [grid]},
        )
        FakeAgent._select_grid = staticmethod(
            lambda app, grid_name: app.GetCalcRelevantObjects("*.ElmNet")[0]
        )

        info = json.loads(mcp_module.get_network_info("Grid"))

        self.assertTrue(info["success"])
        self.assertEqual(info["project"]["name"], "test")
        self.assertEqual(info["study_case"]["name"], "Case 1")
        self.assertEqual(info["grid"]["name"], "Grid")
        self.assertEqual(info["component_counts"]["buses"], 2)
        self.assertEqual(info["component_counts"]["lines"], 1)
        self.assertEqual(info["component_counts"]["circuit_breakers"], 1)
        self.assertEqual(info["out_of_service_counts"]["buses"], 1)
        self.assertEqual(info["circuit_breaker_states"]["closed"], 1)
        self.assertEqual(info["voltage_levels_kv"], [110.0, 345.0])

    def test_state_and_discovery_tools(self):
        project = FakeObject(
            "test",
            "IntPrj",
            r"\user\test.IntPrj",
        )
        case_1 = FakeObject(
            "Case 1",
            "IntCase",
            r"\user\test.IntPrj\Study Cases\Case 1.IntCase",
        )
        case_2 = FakeObject(
            "Case 2",
            "IntCase",
            r"\user\test.IntPrj\Study Cases\Case 2.IntCase",
        )
        bus_1 = FakeObject(
            "Bus 01",
            "ElmTerm",
            r"\user\test.IntPrj\Grid\Bus 01.ElmTerm",
            {"m:u": 1.047, "uknom": 345.0},
        )
        bus_2 = FakeObject(
            "Bus 02",
            "ElmTerm",
            r"\user\test.IntPrj\Grid\Bus 02.ElmTerm",
            {"m:u": 1.049, "uknom": 345.0},
        )

        FakeAgent._shared_app = FakeApplication(
            project=project,
            active_case=case_1,
            study_cases=[case_1, case_2],
            objects={"*.ElmTerm": [bus_1, bus_2]},
        )

        active_project = json.loads(mcp_module.get_active_project())
        self.assertTrue(active_project["success"])
        self.assertEqual(active_project["name"], "test")

        active_case = json.loads(mcp_module.get_active_study_case())
        self.assertTrue(active_case["success"])
        self.assertEqual(active_case["name"], "Case 1")

        parameters = json.loads(
            mcp_module.get_parameters(
                "*.ElmTerm",
                ["m:u", "uknom", "m:u"],
                max_results=1,
            )
        )
        self.assertTrue(parameters["success"])
        self.assertEqual(parameters["variables"], ["m:u", "uknom"])
        self.assertEqual(parameters["total_count"], 2)
        self.assertEqual(parameters["returned_count"], 1)
        self.assertEqual(parameters["results"][0]["name"], "Bus 01")
        self.assertEqual(
            parameters["results"][0]["values"],
            {"m:u": 1.047, "uknom": 345.0},
        )

        objects = json.loads(
            mcp_module.list_objects("*.ElmTerm", max_results=1)
        )
        self.assertEqual(objects["total_count"], 2)
        self.assertEqual(objects["returned_count"], 1)
        self.assertEqual(objects["results"][0]["name"], "Bus 01")

        cases = json.loads(mcp_module.list_study_cases(max_results=10))
        self.assertEqual(cases["total_count"], 2)
        self.assertTrue(cases["results"][0]["is_active"])
        self.assertFalse(cases["results"][1]["is_active"])

        FakeAgent._shared_app = None
        disconnected = json.loads(mcp_module.get_active_project())
        self.assertFalse(disconnected["success"])

    def test_list_components(self):
            bus = FakeObject(
                "Bus 01",
                "ElmTerm",
                r"\user\test.IntPrj\Grid\Bus 01.ElmTerm",
                {"outserv": 0},
            )
            line = FakeObject(
                "Line 01 - 02",
                "ElmLne",
                r"\user\test.IntPrj\Grid\Line 01 - 02.ElmLne",
                {"outserv": 0},
            )
            transformer = FakeObject(
                "Trf 02 - 30",
                "ElmTr2",
                r"\user\test.IntPrj\Grid\Trf 02 - 30.ElmTr2",
                {"outserv": 1},
            )

            FakeAgent._shared_app = FakeApplication(
                project=None,
                active_case=None,
                study_cases=[],
                objects={
                    "*.ElmTerm": [bus],
                    "*.ElmLne": [line],
                    "*.ElmTr2": [transformer],
                    "*.ElmTr3": [],
                    "*.ElmCoup": [],
                },
            )

            buses = json.loads(
                mcp_module.list_components("buses", max_results=10)
            )
            self.assertTrue(buses["success"])
            self.assertEqual(buses["total_count"], 1)
            self.assertEqual(buses["results"][0]["name"], "Bus 01")

            branches = json.loads(
                mcp_module.list_components("branches", max_results=10)
            )
            self.assertTrue(branches["success"])
            self.assertEqual(branches["total_count"], 2)
            self.assertEqual(branches["returned_count"], 2)
            self.assertEqual(
                {item["class_name"] for item in branches["results"]},
                {"ElmLne", "ElmTr2"},
            )

            transformers = json.loads(
                mcp_module.list_components(
                    "transformers",
                    max_results=10,
                )
            )
            self.assertEqual(transformers["total_count"], 1)
            self.assertTrue(
                transformers["results"][0]["out_of_service"]
            )

            limited = json.loads(
                mcp_module.list_components("branches", max_results=1)
            )
            self.assertEqual(limited["total_count"], 2)
            self.assertEqual(limited["returned_count"], 1)

            unsupported = json.loads(
                mcp_module.list_components("unknown")
            )
            self.assertFalse(unsupported["success"])
            self.assertIn(
                "buses",
                unsupported["supported_component_types"],
            )


if __name__ == "__main__":
    unittest.main()
