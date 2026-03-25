document.addEventListener('DOMContentLoaded', function() {
    const longUrlInput = document.getElementById('longUrl');
    const customCodeInput = document.getElementById('customCode');
    const expiresDaysInput = document.getElementById('expiresDays');
    const passwordInput = document.getElementById('password');
    const shortenBtn = document.getElementById('shortenBtn');
    const loadingDiv = document.getElementById('loading');
    const resultDiv = document.getElementById('result');
    const errorDiv = document.getElementById('error');
    const shortUrlInput = document.getElementById('shortUrl');
    const copyBtn = document.getElementById('copyBtn');
    const createdAtSpan = document.getElementById('createdAt');
    const clickCountSpan = document.getElementById('clickCount');
    const errorMessageSpan = document.getElementById('errorMessage');
    const qrLink = document.getElementById('qrLink');
    let currentShortCode = '';

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
        
        const requestBody = {
            long_url: longUrl
        };
        
        if (customCodeInput.value.trim()) {
            requestBody.custom_code = customCodeInput.value.trim();
        }
        if (expiresDaysInput.value) {
            requestBody.expires_days = parseInt(expiresDaysInput.value);
        }
        if (passwordInput.value) {
            requestBody.password = passwordInput.value;
        }
        
        try {
            const response = await fetch('/shorten', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });
            
            const data = await response.json();
            
            if (response.ok) {
                currentShortCode = data.short_code;
                shortUrlInput.value = data.short_url;
                createdAtSpan.textContent = new Date(data.created_at).toLocaleString();
                clickCountSpan.textContent = data.clicks;
                qrLink.href = `/qr/${currentShortCode}`;
                resultDiv.style.display = 'block';
                longUrlInput.value = '';
                customCodeInput.value = '';
                expiresDaysInput.value = '';
                passwordInput.value = '';
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