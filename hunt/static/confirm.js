// Unobtrusive confirmation dialog for links with data-confirm attribute
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('a[data-confirm]').forEach(function(link) {
    link.addEventListener('click', function(e) {
      if (!confirm(this.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });
});
