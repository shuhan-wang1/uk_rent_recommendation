# test_async.py
import sys
print(f"Python version: {sys.version}")

try:
    import asgiref
    print(f"✓ asgiref installed: {asgiref.__version__}")
except ImportError:
    print("✗ asgiref NOT installed")

try:
    import flask
    print(f"✓ Flask installed: {flask.__version__}")
    
    # Test if Flask can handle async
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/test')
    async def test():
        return "async works"
    
    print("✓ Flask async support is working!")
except Exception as e:
    print(f"✗ Flask async error: {e}")