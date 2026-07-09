/*Universidad Politécnica de Victoria, Ciudad Victoria. Tamaulipas (18 de Abril de 2025)
Ingeniería en Tecnologías de la información
Proyecto final de la materia de "Base de datos", cursada con el maestro: ING. LUIS ANTONIO GONZALEZ CASTRO 
Integrantes del proyecto: Joshua André Alvarado Tovar, Ingridh Maricela Gracia Flores, Juan Antonio Manzano Ceja, Angel Guadalupe Rivera Portillo.
El presente código forma parte de nuestro proyecto final, donde encontrará la estructura necesitada para el correcto funcionamiento de nuestro proyecto:*/

document.addEventListener('DOMContentLoaded', function() {
    // Validación de contraseña
    const passwordInput = document.getElementById('password');
    const strengthBars = document.querySelectorAll('.strength-bar');
    const strengthText = document.querySelector('.strength-text');
    
    if (passwordInput) {
      passwordInput.addEventListener('input', function() {
        const password = this.value;
        let strength = 0;
        
        // Longitud mínima
        if (password.length >= 8) strength++;
        // Contiene números
        if (/\d/.test(password)) strength++;
        // Contiene mayúsculas y minúsculas
        if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
        // Contiene caracteres especiales
        if (/[^a-zA-Z0-9]/.test(password)) strength++;
        
        // Actualizar barras de fortaleza
        strengthBars.forEach((bar, index) => {
          bar.style.background = index < strength ? getStrengthColor(strength) : '#555';
        });
        
        // Actualizar texto
        const strengthMessages = ['Débil', 'Moderada', 'Fuerte', 'Muy fuerte'];
        strengthText.textContent = `Seguridad: ${strengthMessages[strength-1] || 'Débil'}`;
        strengthText.style.color = getStrengthColor(strength);
      });
    }
    
    function getStrengthColor(strength) {
      const colors = ['#ff4d4d', '#ffa64d', '#4dff4d', '#00b300'];
      return colors[strength-1] || '#ff4d4d';
    }
    
    // Validación de confirmación de contraseña
    const confirmPasswordInput = document.getElementById('confirm-password');
    if (confirmPasswordInput) {
      confirmPasswordInput.addEventListener('input', function() {
        const password = passwordInput.value;
        const confirmPassword = this.value;
        
        if (confirmPassword && password !== confirmPassword) {
          this.setCustomValidity("Las contraseñas no coinciden");
        } else {
          this.setCustomValidity("");
        }
      });
    }
  });