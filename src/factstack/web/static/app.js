// FactStack Web UI JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const questionInput = document.getElementById('question-input');
    const askBtn = document.getElementById('ask-btn');
    const crossLingualCheckbox = document.getElementById('cross-lingual');
    const translationModeSelect = document.getElementById('translation-mode');
    const answerSection = document.getElementById('answer-section');
    const errorSection = document.getElementById('error-section');

    // Ask button click handler
    askBtn.addEventListener('click', function() {
        askQuestion();
    });

    // Enter key handler (Ctrl+Enter or Cmd+Enter to submit)
    questionInput.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            askQuestion();
        }
    });

    // Toggle translation mode based on cross-lingual checkbox
    crossLingualCheckbox.addEventListener('change', function() {
        translationModeSelect.disabled = !this.checked;
    });

    async function askQuestion() {
        const question = questionInput.value.trim();
        if (!question) {
            showError('Please enter a question.');
            return;
        }

        // Show loading state
        setLoading(true);
        hideError();
        hideAnswer();

        try {
            const response = await fetch('/api/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    question: question,
                    cross_lingual: crossLingualCheckbox.checked,
                    translation_mode: translationModeSelect.value,
                    top_k: 8
                })
            });

            const data = await response.json();

            if (data.success) {
                displayAnswer(data);
            } else {
                showError(data.error || 'An error occurred while processing your question.');
            }
        } catch (error) {
            // Log minimal error info to avoid exposing sensitive details
            console.error('Request failed');
            showError('Failed to connect to the server. Please make sure the server is running.');
        } finally {
            setLoading(false);
        }
    }

    function setLoading(loading) {
        const btnText = askBtn.querySelector('.btn-text');
        const btnLoading = askBtn.querySelector('.btn-loading');
        
        askBtn.disabled = loading;
        btnText.style.display = loading ? 'none' : 'inline';
        btnLoading.style.display = loading ? 'inline' : 'none';
    }

    function displayAnswer(data) {
        // Query language badge
        const queryLangEl = document.getElementById('query-lang');
        const langEmoji = data.query_language === 'zh' ? '🇨🇳' : data.query_language === 'mixed' ? '🌐' : '🇬🇧';
        queryLangEl.textContent = `${langEmoji} ${data.query_language.toUpperCase()}`;

        // Confidence badge
        const confidenceEl = document.getElementById('confidence');
        const confidencePercent = Math.round(data.confidence * 100);
        confidenceEl.textContent = `Confidence: ${confidencePercent}%`;
        confidenceEl.className = 'badge';
        if (confidencePercent >= 70) {
            confidenceEl.classList.add('success');
        } else if (confidencePercent >= 40) {
            confidenceEl.classList.add('warning');
        } else {
            confidenceEl.classList.add('error');
        }

        // Answer content
        const answerContentEl = document.getElementById('answer-content');
        answerContentEl.textContent = data.answer;

        // Refusal notice
        const refusalNotice = document.getElementById('refusal-notice');
        const refusalReason = document.getElementById('refusal-reason');
        if (data.is_refusal) {
            refusalNotice.style.display = 'flex';
            refusalReason.textContent = data.refusal_reason || 'The system could not confidently answer this question.';
        } else {
            refusalNotice.style.display = 'none';
        }

        // Citations
        const citationsList = document.getElementById('citations-list');
        citationsList.innerHTML = '';
        
        if (data.citations && data.citations.length > 0) {
            data.citations.forEach(citation => {
                const card = document.createElement('div');
                card.className = 'citation-card';
                card.innerHTML = `
                    <div class="citation-header">
                        <div>
                            <span class="citation-id">[C${citation.id}]</span>
                            <span class="citation-source">${citation.source}</span>
                        </div>
                        <span class="citation-score">Score: ${citation.score}</span>
                    </div>
                    <div class="citation-text">${escapeHtml(citation.text)}</div>
                `;
                citationsList.appendChild(card);
            });
            document.getElementById('citations-section').style.display = 'block';
        } else {
            document.getElementById('citations-section').style.display = 'none';
        }

        // Missing info
        const missingInfoSection = document.getElementById('missing-info-section');
        const missingInfoList = document.getElementById('missing-info-list');
        if (data.missing_info && data.missing_info.length > 0) {
            missingInfoList.innerHTML = data.missing_info.map(info => `<li>${escapeHtml(info)}</li>`).join('');
            missingInfoSection.style.display = 'block';
        } else {
            missingInfoSection.style.display = 'none';
        }

        // Run ID
        document.getElementById('run-id').textContent = `Run ID: ${data.run_id}`;

        // Show answer section
        answerSection.style.display = 'block';
    }

    function showError(message) {
        document.getElementById('error-message').textContent = message;
        errorSection.style.display = 'block';
    }

    function hideError() {
        errorSection.style.display = 'none';
    }

    function hideAnswer() {
        answerSection.style.display = 'none';
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
