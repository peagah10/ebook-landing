// Script para melhorar a experiência do usuário
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('payment-form');
    
    if (form) {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processando...';
            submitBtn.disabled = true;
        });
    }
});