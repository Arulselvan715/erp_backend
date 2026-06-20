import flask

def patch_render_template():
    original_render_template = flask.render_template

    def custom_render_template(template_name_or_list, **context):
        from flask import request, jsonify
        # Check if request expects JSON
        accept_header = request.headers.get("Accept", "")
        if (request.is_json or 
            "application/json" in accept_header or 
            request.path.startswith("/api/") or
            request.args.get("format") == "json"):
            
            from routes.utils import serialize
            serialized_context = {}
            for k, v in context.items():
                if k not in ["current_user", "g", "request", "session", "bootstrap"]:
                    serialized_context[k] = serialize(v)
            
            primary_list = None
            primary_key = None
            list_keys = ["products", "orders", "boms", "customers", "vendors", "ledger", "movements", "logs"]
            
            for k in list_keys:
                if k in serialized_context:
                    primary_list = serialized_context[k]
                    primary_key = k
                    break
            
            if primary_list is not None and isinstance(primary_list, list):
                return jsonify({
                    "data": primary_list,
                    "total": len(primary_list)
                })
            
            if len(serialized_context) == 1:
                key = list(serialized_context.keys())[0]
                return jsonify(serialized_context[key])
            
            return jsonify(serialized_context)
        return original_render_template(template_name_or_list, **context)

    flask.render_template = custom_render_template
