'use strict';
// A classic bootstrap can run from file:, where ES modules and API calls cannot.
(() => {
  function start() {
    if (location.protocol !== 'file:') {
      const application = document.createElement('script');
      application.type = 'module';
      application.src = './app.js';
      // A server started before these files were saved still serves index.html but 404s on newer
      // modules. Without this the page looks normal yet has no listeners at all, and the only clue
      // is in the browser console. Say it on the page instead.
      application.onerror = () => {
        const stale = {
          en: 'The dashboard scripts failed to load, so nothing on this page is active. The running server is older than these files: stop it, start it again, then reload.',
          kk: 'Бақылау тақтасының скриптері жүктелмеді, сондықтан беттегі ештеңе жұмыс істемейді. Іске қосылған сервер осы файлдардан ескі: оны тоқтатып, қайта іске қосыңыз да, бетті жаңартыңыз.',
          ru: 'Скрипты панели не загрузились, поэтому на странице ничего не работает. Запущенный сервер старше этих файлов: остановите его, запустите заново и обновите страницу.',
        };
        const language = String(navigator.language || 'en').toLowerCase().replaceAll('_', '-').split('-')[0];
        const notice = document.createElement('p');
        notice.className = 'error';
        notice.setAttribute('role', 'alert');
        notice.textContent = stale[language === 'kz' ? 'kk' : Object.hasOwn(stale, language) ? language : 'en'];
        (document.querySelector('main') || document.body).prepend(notice);
      };
      document.head.append(application);
      return;
    }
    const messages = {
      en: {
        title: 'Open the local dashboard',
        explanation: 'This HTML file is a preview. Money Graph needs its local Python server to load data and analyze uploads.',
        open: 'Open Money Graph →',
        instruction: 'If the dashboard is not running, start it from the project folder:',
        port: 'Using a different port? Open the address printed by the server.',
        privacy: 'Analysis stays on this computer. No cloud service is required.',
      },
      kk: {
        title: 'Жергілікті бақылау тақтасын ашыңыз',
        explanation: 'Бұл HTML файлы тек алдын ала қарауға арналған. Деректерді жүктеу және файлдарды талдау үшін Money Graph жергілікті Python серверін қажет етеді.',
        open: 'Money Graph ашу →',
        instruction: 'Бақылау тақтасы іске қосылмаса, жоба қалтасынан мына пәрменді орындаңыз:',
        port: 'Басқа портты қолданасыз ба? Сервер көрсеткен мекенжайды ашыңыз.',
        privacy: 'Талдау осы компьютерде орындалады. Бұлттық қызмет қажет емес.',
      },
      ru: {
        title: 'Откройте локальную панель',
        explanation: 'Этот HTML-файл предназначен для предпросмотра. Для загрузки данных и анализа файлов Money Graph нужен локальный сервер Python.',
        open: 'Открыть Money Graph →',
        instruction: 'Если панель ещё не запущена, выполните команду из папки проекта:',
        port: 'Используете другой порт? Откройте адрес, указанный сервером.',
        privacy: 'Анализ выполняется на этом компьютере. Облачные сервисы не нужны.',
      },
    };
    const normalize = value => {
      const language = String(value || '').toLowerCase().replaceAll('_', '-').split('-')[0];
      return language === 'kz' ? 'kk' : Object.hasOwn(messages, language) ? language : null;
    };
    let saved;
    try { saved = normalize(localStorage.getItem('money-graph.locale')); }
    catch { /* File-origin storage may be unavailable; use the browser language. */ }
    const language = saved || navigator.languages.map(normalize).find(Boolean) || 'en';
    const copy = messages[language];
    document.documentElement.lang = language;
    document.title = `Money Graph · ${copy.title}`;
    const node = (tag, text, className) => {
      const value = document.createElement(tag);
      if (text) value.textContent = text;
      if (className) value.className = className;
      return value;
    };
    const header = node('header');
    const brand = node('div');
    brand.append(node('p', 'HACKALEM / FINANCE', 'eyebrow'), node('h1', 'Money Graph'));
    header.append(brand);
    const main = node('main');
    main.id = 'file-preview';
    main.style.maxWidth = '820px';
    main.style.paddingTop = '48px';
    const panel = node('section', undefined, 'panel');
    panel.append(node('h2', copy.title), node('p', copy.explanation));
    const link = node('a', copy.open);
    link.href = 'http://127.0.0.1:8765/';
    link.style.display = 'inline-block';
    link.style.margin = '12px 0';
    link.style.fontWeight = '700';
    panel.append(link, node('p', copy.instruction));
    const command = node('pre');
    command.style.whiteSpace = 'pre-wrap';
    command.style.overflowWrap = 'anywhere';
    command.style.padding = '16px';
    command.style.background = '#eef5f2';
    command.style.borderRadius = '6px';
    command.append(node('code', './scripts/money-graph.sh --serve --upload-only'));
    panel.append(command, node('p', copy.port, 'muted'));
    main.append(panel, node('p', copy.privacy, 'muted'));
    document.body.replaceChildren(header, main);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
