from app import create_app
from app.api import api

app = create_app()

# Print all registered routes and rules for debugging
print("All registered API routes:")
for rule in app.url_map.iter_rules():
    print(f"Route: {rule}, Endpoint: {rule.endpoint}")

print("\nAPI namespaces:")
for ns in api.namespaces:
    print(f"Namespace: {ns.name}")
    for resource, urls, kwargs in ns.resources:
        print(f"  Resource: {resource.__name__}, URLs: {urls}")

if __name__ == "__main__":
    # Run in debug mode
    app.run(debug=True, port=5000)