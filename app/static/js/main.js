document.addEventListener('DOMContentLoaded', function() {
    const longUrlInput = document.getElementById('longUrl');
    const shortenBtn = document.getElementById('shortenBtn');
    const loadingDiv = document.getElementById('loading');
    const resultDiv = document.getElementById('result');
    const errorDiv = document.getElementById('error');
    const shortUrlInput = document.getElementById('shortUrl');
    const copyBtn = document.getElementById('copyBtn');
    const createdAtSpan = document.getElementById('createdAt');
    const clickCountSpan = document.getElementById('clickCount');
    const errorMessageSpan = document.getElementById('errorMessage');

    shortenBtn.addEventListener('click', async function() {
        const longUrl = longUrlInput.value.trim();
        
        if (!longUrl) {
            showError('Please enter a URL');
            return;
        }
        
        try {
            new URL(longUrl);
        } catch(e) {
            showError('Please enter a valid URL (include https://)');
            return;
        }
        
        resultDiv.style.display = 'none';
        errorDiv.style.display = 'none';
        loadingDiv.style.display = 'flex';
        shortenBtn.disabled = true;
        
        try {
            const response = await fetch('/shorten', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    long_url: longUrl
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                shortUrlInput.value = data.short_url;
                createdAtSpan.textContent = new Date(data.created_at).toLocaleString();
                clickCountSpan.textContent = data.clicks;
                resultDiv.style.display = 'block';
                longUrlInput.value = '';
            } else {
                showError(data.detail || 'Something went wrong');
            }
        } catch(error) {
            showError('Failed to create short URL. Please try again.');
        } finally {
            loadingDiv.style.display = 'none';
            shortenBtn.disabled = false;
        }
    });
    
    copyBtn.addEventListener('click', async function() {
        const shortUrl = shortUrlInput.value;
        
        if (shortUrl) {
            try {
                await navigator.clipboard.writeText(shortUrl);
                const originalText = copyBtn.textContent;
                copyBtn.textContent = '✅ Copied!';
                setTimeout(() => {
                    copyBtn.textContent = originalText;
                }, 2000);
            } catch(err) {
                shortUrlInput.select();
                document.execCommand('copy');
                const originalText = copyBtn.textContent;
                copyBtn.textContent = '✅ Copied!';
                setTimeout(() => {
                    copyBtn.textContent = originalText;
                }, 2000);
            }
        }
    });
    
    longUrlInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            shortenBtn.click();
        }
    });
    
    function showError(message) {
        errorMessageSpan.textContent = message;
        errorDiv.style.display = 'block';
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    }
});