"""Minimal, dependency-free builder for native draw.io (.drawio) diagrams.

All cells are placed with absolute coordinates on the root layer so files stay
easy to diff and to edit in diagrams.net. AWS shapes use the official
`mxgraph.aws4` stencil library that ships with draw.io.

Usage:
    from drawio_kit import Diagram, write_file
    d = Diagram("my-diagram", "Title", width=1600, height=1000)
    d.group("acct", 40, 120, 700, 500, "Workload account", kind="account")
    d.aws("gw", 200, 200, "bedrock", "AgentCore Gateway")
    d.box("svc", 400, 200, 160, 60, "Adapter")
    d.edge("gw", "svc", "SigV4")
    write_file("out.drawio", [d])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.sax.saxutils import escape

# Shared visual language (navy / off-white / amber, consistent with the
# AgentCore series) plus AWS category colours for service icons.
NAVY = "#142B49"
INK = "#232F3E"
AMBER = "#EDB44C"
AMBER_DARK = "#B7791F"
PAPER = "#FFFFFF"
MIST = "#F4F6F8"
LINE = "#CBD1D6"
RED = "#C7254E"
GREEN = "#2E7D32"
TEAL = "#00A4A6"

AWS_CATEGORY = {
    "compute": "#ED7100",
    "network": "#8C4FFF",
    "security": "#DD344C",
    "management": "#E7157B",
    "integration": "#E7157B",
    "ml": "#01A88D",
    "storage": "#7AA116",
    "database": "#C925D1",
    "devtools": "#C925D1",
    "general": "#232F3E",
}

# resIcon name -> category. Only names verified to render in draw.io 24.x.
AWS_ICONS = {
    "bedrock": "ml",
    "lambda": "compute",
    "ecs": "compute",
    "fargate": "compute",
    "vpc_lattice": "network",
    "vpc_privatelink": "network",
    "direct_connect": "network",
    "transit_gateway": "network",
    "route_53": "network",
    "api_gateway": "integration",
    "eventbridge": "integration",
    "step_functions": "integration",
    "key_management_service": "security",
    "secrets_manager": "security",
    "cognito": "security",
    "verified_permissions": "security",
    "identity_and_access_management": "security",
    "guardduty": "security",
    "security_hub": "security",
    "waf": "security",
    "cloudwatch": "management",
    "cloudtrail": "management",
    "config": "management",
    "organizations": "management",
    "control_tower": "management",
    "xray": "devtools",
    "codepipeline": "devtools",
    "codebuild": "devtools",
    "s3": "storage",
    "dynamodb": "database",
    "rds": "database",
    "users": "general",
    "client": "general",
    "corporate_data_center": "general",
}

GROUPS = {
    "cloud": "grIcon=mxgraph.aws4.group_aws_cloud_alt;strokeColor=#232F3E;fontColor=#232F3E;dashed=0;",
    "region": "grIcon=mxgraph.aws4.group_region;strokeColor=#00A4A6;fontColor=#147EBA;dashed=1;",
    "account": "grIcon=mxgraph.aws4.group_account;strokeColor=#CD2264;fontColor=#CD2264;dashed=0;",
    "vpc": "grIcon=mxgraph.aws4.group_vpc2;strokeColor=#8C4FFF;fontColor=#8C4FFF;dashed=0;",
    "subnet": "grIcon=mxgraph.aws4.group_security_group;grStroke=0;strokeColor=#00A4A6;fillColor=#E6F6F7;fontColor=#147EBA;dashed=0;",
    "datacenter": "grIcon=mxgraph.aws4.group_corporate_data_center;strokeColor=#7D8998;fontColor=#5A6C86;dashed=0;",
    "onprem": "grIcon=mxgraph.aws4.group_on_premise;strokeColor=#7D8998;fontColor=#5A6C86;dashed=0;",
}


def _attr(value: str) -> str:
    return escape(value, {'"': "&quot;", "\n": "&#xa;"})


@dataclass
class Diagram:
    slug: str
    title: str
    width: int = 1600
    height: int = 1000
    subtitle: str = ""
    footer: str = ""
    background: str = PAPER
    cells: list[str] = field(default_factory=list)
    ids: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        # Locked full-page rectangle: draw.io exports crop to content, so this
        # keeps the page margins (and background) in the exported SVG.
        self._vertex("page", 0, 0, self.width, self.height, "",
                     f"rounded=0;html=1;fillColor={self.background};strokeColor=none;locked=1;")
        self.text("title", 40, 20, self.width - 80, 44, self.title, size=26, bold=True)
        if self.subtitle:
            self.text("subtitle", 40, 62, self.width - 80, 30, self.subtitle, size=15)
        if self.footer:
            self.text("footer", 40, self.height - 46, self.width - 80, 30, self.footer, size=12, color="#5A6C86")

    # -- primitives -------------------------------------------------------
    def _vertex(self, cid: str, x: float, y: float, w: float, h: float, value: str, style: str) -> str:
        if cid in self.ids:
            raise ValueError(f"duplicate cell id: {cid}")
        self.ids.add(cid)
        self.cells.append(
            f'<mxCell id="{cid}" value="{_attr(value)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
        )
        return cid

    def text(self, cid, x, y, w, h, value, size=13, bold=False, color=NAVY, align="left", italic=False):
        style = (
            f"text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;align={align};verticalAlign=middle;"
            f"fontFamily=Helvetica;fontSize={size};fontColor={color};fontStyle={(1 if bold else 0) + (2 if italic else 0)};"
        )
        return self._vertex(cid, x, y, w, h, value, style)

    def box(self, cid, x, y, w, h, value, fill=MIST, stroke=NAVY, font=NAVY, size=13, bold=False,
            rounded=True, dashed=False, shape="", stroke_width=1.5, align="center"):
        style = (
            f"{shape}rounded={1 if rounded else 0};arcSize=8;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
            f"strokeWidth={stroke_width};fontFamily=Helvetica;fontSize={size};fontColor={font};"
            f"fontStyle={1 if bold else 0};dashed={1 if dashed else 0};align={align};spacing=6;"
        )
        return self._vertex(cid, x, y, w, h, value, style)

    def diamond(self, cid, x, y, w, h, value, fill="#FFF4DB", stroke=AMBER_DARK, size=12):
        return self.box(cid, x, y, w, h, value, fill=fill, stroke=stroke, size=size, bold=True,
                        rounded=False, shape="rhombus;")

    def badge(self, cid, x, y, value, fill=AMBER, font=NAVY, w=34, h=34):
        style = (
            f"ellipse;whiteSpace=wrap;html=1;fillColor={fill};strokeColor=none;fontFamily=Helvetica;"
            f"fontSize=14;fontStyle=1;fontColor={font};"
        )
        return self._vertex(cid, x, y, w, h, value, style)

    def group(self, cid, x, y, w, h, label, kind="cloud", fill="none"):
        base = (
            "points=[];outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=13;fontStyle=1;"
            "container=0;pointerEvents=0;collapsible=0;recursiveResize=0;shape=mxgraph.aws4.group;"
            f"fillColor={fill};verticalAlign=top;align=left;spacingLeft=30;fontFamily=Helvetica;"
        )
        if kind == "plain":
            style = (
                f"rounded=1;arcSize=2;html=1;whiteSpace=wrap;fillColor={fill};strokeColor={LINE};dashed=1;"
                "verticalAlign=top;align=left;spacingLeft=10;spacingTop=4;fontFamily=Helvetica;fontSize=13;"
                f"fontStyle=1;fontColor={NAVY};"
            )
        else:
            style = base + GROUPS[kind]
        return self._vertex(cid, x, y, w, h, label, style)

    def aws(self, cid, x, y, icon, label, size=56, font_size=11):
        if icon not in AWS_ICONS:
            raise KeyError(f"unknown/unverified AWS icon: {icon}")
        color = AWS_CATEGORY[AWS_ICONS[icon]]
        style = (
            "sketch=0;outlineConnect=0;fontColor=#232F3E;strokeColor=#ffffff;dashed=0;"
            "verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;"
            f"fontFamily=Helvetica;fontSize={font_size};fontStyle=0;aspect=fixed;fillColor={color};"
            f"shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{icon};"
        )
        return self._vertex(cid, x, y, size, size, label, style)

    def edge(self, src, tgt, label="", color=NAVY, dashed=False, width=1.6, both=False,
             exit=None, entry=None, label_bg=PAPER, curved=False, waypoints=None, font_size=11):
        cid = f"e_{src}_{tgt}"
        n = 2
        while cid in self.ids:
            cid = f"e_{src}_{tgt}_{n}"
            n += 1
        self.ids.add(cid)
        style = (
            f"edgeStyle={'none' if curved else 'orthogonalEdgeStyle'};rounded=1;html=1;"
            f"endArrow=block;endFill=1;startArrow={'block' if both else 'none'};startFill=1;"
            f"strokeColor={color};strokeWidth={width};dashed={1 if dashed else 0};fontFamily=Helvetica;"
            f"fontSize={font_size};fontColor={NAVY};labelBackgroundColor={label_bg};"
        )
        if exit:
            style += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
        if entry:
            style += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
        points = ""
        if waypoints:
            points = '<Array as="points">' + "".join(
                f'<mxPoint x="{px}" y="{py}"/>' for px, py in waypoints) + "</Array>"
        self.cells.append(
            f'<mxCell id="{cid}" value="{_attr(label)}" style="{style}" edge="1" parent="1" '
            f'source="{src}" target="{tgt}"><mxGeometry relative="1" as="geometry">{points}</mxGeometry></mxCell>'
        )
        return cid

    def legend(self, x, y, items, title="Legend"):
        """items: list of (label, color, dashed)."""
        self.text("legend_title", x, y, 260, 22, title, size=12, bold=True)
        for i, (label, color, dashed) in enumerate(items):
            yy = y + 28 + i * 24
            self.box(f"legend_sw{i}", x, yy + 5, 28, 4, "", fill=color, stroke=color,
                     rounded=False, dashed=dashed, stroke_width=1)
            self.text(f"legend_l{i}", x + 36, yy - 4, 260, 22, label, size=11)

    # -- serialisation ----------------------------------------------------
    def xml(self) -> str:
        body = "".join(self.cells)
        return (
            f'<diagram id="{self.slug}" name="{_attr(self.title)}">'
            f'<mxGraphModel dx="{self.width}" dy="{self.height}" grid="1" gridSize="10" guides="1" '
            f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
            f'pageWidth="{self.width}" pageHeight="{self.height}" background="{self.background}" math="0" shadow="0">'
            f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>{body}</root></mxGraphModel></diagram>'
        )


def write_file(path: str, diagrams: list[Diagram]) -> None:
    content = (
        '<mxfile host="app.diagrams.net" agent="mcp-architect drawio_kit" version="24.7.17" type="device">'
        + "".join(d.xml() for d in diagrams)
        + "</mxfile>\n"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
