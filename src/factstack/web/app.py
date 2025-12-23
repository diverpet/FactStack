"""Web frontend for FactStack."""

import json
import os
from pathlib import Path
from typing import Optional

from flask import Flask, render_template, request, jsonify

from factstack.config import Config
from factstack.ask import ask, get_llm
from factstack.pipeline.query_language import detect_language


def create_app(db_dir: Optional[str] = None) -> Flask:
    """Create and configure the Flask application.
    
    Args:
        db_dir: Path to the database directory
    
    Returns:
        Configured Flask application
    """
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
        static_folder=os.path.join(os.path.dirname(__file__), 'static')
    )
    
    # Configuration
    app.config['DB_DIR'] = db_dir or os.environ.get('FACTSTACK_DB_DIR', './db')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'factstack-dev-key')
    
    @app.route('/')
    def index():
        """Render the main page."""
        config = Config.from_env()
        return render_template(
            'index.html',
            llm_provider=config.llm.provider,
            llm_model=config.llm.model
        )
    
    @app.route('/api/ask', methods=['POST'])
    def api_ask():
        """API endpoint for asking questions."""
        try:
            data = request.get_json()
            question = data.get('question', '').strip()
            
            if not question:
                return jsonify({
                    'success': False,
                    'error': 'Question is required'
                }), 400
            
            # Get options from request
            cross_lingual = data.get('cross_lingual', True)
            translation_mode = data.get('translation_mode', 'rule')
            top_k = data.get('top_k', 8)
            
            # Detect language
            query_lang = detect_language(question)
            
            # Get database directory
            db_dir = Path(app.config['DB_DIR'])
            if not db_dir.exists():
                return jsonify({
                    'success': False,
                    'error': f'Database directory not found: {db_dir}. Please run ingestion first.'
                }), 400
            
            # Run the RAG pipeline
            config = Config.from_env()
            result = ask(
                question=question,
                db_dir=db_dir,
                config=config,
                top_k=top_k,
                save_artifacts=True,
                cross_lingual=cross_lingual,
                translate=cross_lingual,
                translation_mode=translation_mode
            )
            
            # Format response
            response = {
                'success': True,
                'question': question,
                'query_language': query_lang,
                'answer': result.answer.answer,
                'confidence': result.answer.confidence,
                'is_refusal': result.answer.is_refusal,
                'refusal_reason': result.answer.refusal_reason,
                'citations': [
                    {
                        'id': i + 1,
                        'chunk_id': cit.chunk_id,
                        'source': cit.source,
                        'text': cit.text[:300] + '...' if len(cit.text) > 300 else cit.text,
                        'score': round(cit.score, 3)
                    }
                    for i, cit in enumerate(result.answer.citations)
                ],
                'missing_info': result.answer.missing_info or [],
                'run_id': result.run_id,
                'trace_path': result.trace_path
            }
            
            return jsonify(response)
            
        except Exception as e:
            # Only print detailed stack traces in debug mode
            if app.debug:
                import traceback
                traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/config', methods=['GET'])
    def api_config():
        """Get current configuration."""
        config = Config.from_env()
        db_dir = Path(app.config['DB_DIR'])
        
        return jsonify({
            'llm_provider': config.llm.provider,
            'llm_model': config.llm.model,
            'embedding_model': config.embedding.model,
            'db_exists': db_dir.exists(),
            'db_path': str(db_dir)
        })
    
    return app


def main():
    """Run the web server."""
    import argparse
    
    parser = argparse.ArgumentParser(description='FactStack Web UI')
    parser.add_argument(
        '--db', '-d',
        type=str,
        default='./db',
        help='Database directory (default: ./db)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=5000,
        help='Port to listen on (default: 5000)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )
    
    args = parser.parse_args()
    
    # Check if database exists
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"⚠️  Warning: Database directory '{db_path}' does not exist.")
        print("   Run `python -m factstack.ingest` first to create the database.")
        print()
    
    app = create_app(args.db)
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    🔍 FactStack Web UI                       ║
╠══════════════════════════════════════════════════════════════╣
║  Evidence-first RAG Q&A for Technical Documentation          ║
╚══════════════════════════════════════════════════════════════╝

🌐 Server starting at: http://{args.host}:{args.port}
📂 Database: {args.db}
🔧 Debug mode: {'ON' if args.debug else 'OFF'}

Press Ctrl+C to stop the server.
""")
    
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
