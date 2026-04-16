export function ThemeInitScript(): React.ReactNode {
  const script = `
    (function() {
      try {
        var theme = localStorage.getItem('agents-platform-theme');
        if (theme === 'dark') {
          document.documentElement.classList.add('dark');
        } else if (theme === 'cool' || theme === 'warm' || theme === 'purple') {
          document.documentElement.setAttribute('data-theme', theme);
        }
      } catch(e) {}
    })();
  `;

  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
