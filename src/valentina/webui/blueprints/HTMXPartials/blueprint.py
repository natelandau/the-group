"""Blueprints for serving HTMX Partials."""

from quart import Blueprint

from valentina.webui.constants import TableType, TextType

from .route import EditTableView, EditTextView

blueprint = Blueprint("partials", __name__, url_prefix="/partials")


for i in TableType:
    blueprint.add_url_rule(
        f"/table/{i.value.route_suffix}",
        view_func=EditTableView.as_view(i.value.route_suffix, table_type=i),
        methods=["GET", "POST", "DELETE", "PUT"],
    )

for t in TextType:
    blueprint.add_url_rule(
        f"/text/{t.value.route_suffix}",
        view_func=EditTextView.as_view(t.value.route_suffix, text_type=t),
        methods=["GET", "POST", "PUT"],
    )
