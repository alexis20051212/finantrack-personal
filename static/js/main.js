// FinanTrack - JavaScript principal

// Ocultar alertas después de 5 segundos
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.remove();
                }
            }, 300);
        }, 5000);
    });
});

// Validación de formularios en tiempo real
const forms = document.querySelectorAll('form');
forms.forEach(form => {
    form.addEventListener('submit', function(e) {
        const password = form.querySelector('#password');
        const confirmPassword = form.querySelector('#confirm_password');
        
        if (password && confirmPassword && password.value !== confirmPassword.value) {
            e.preventDefault();
            alert('❌ Las contraseñas no coinciden');
            confirmPassword.style.borderColor = '#dc3545';
            password.style.borderColor = '#dc3545';
        }
    });
});

// Confirmación para eliminar
const deleteLinks = document.querySelectorAll('.btn-delete');
deleteLinks.forEach(link => {
    link.addEventListener('click', function(e) {
        if (!confirm('¿Estás seguro de que quieres eliminar este movimiento?')) {
            e.preventDefault();
        }
    });
});

// Formatear números en inputs de monto
const montoInputs = document.querySelectorAll('input[type="number"]');
montoInputs.forEach(input => {
    input.addEventListener('change', function() {
        if (this.value) {
            this.value = parseFloat(this.value).toFixed(2);
        }
    });
});

// Validación de formularios
document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const password = form.querySelector('#password');
            const confirmPassword = form.querySelector('#confirm_password');
            
            if (password && confirmPassword && password.value !== confirmPassword.value) {
                e.preventDefault();
                alert('❌ Las contraseñas no coinciden');
            }
        });
    });
});