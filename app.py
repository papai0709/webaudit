from flask import Flask, render_template, request, jsonify
from analyzer import WebsiteAnalyzer
import traceback

app = Flask(__name__)

@app.route('/')
def index():
    """Render the main dashboard page"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Analyze a website and return results"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        max_pages = int(data.get('max_pages', 20))
        
        if not url:
            return jsonify({'error': 'Please provide a valid URL'}), 400
        
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Create analyzer and run analysis
        analyzer = WebsiteAnalyzer(url, max_pages=max_pages)
        results = analyzer.analyze()
        
        return jsonify(results)
    
    except Exception as e:
        print(f"Error analyzing website: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Failed to analyze website: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
