<template>
  <div id="app">
    <Header />
    <main class="container">
      <router-view />
    </main>
    <footer class="footer">
      <p>非遗大师 - 中国非物质文化遗产数字化平台</p>
    </footer>
  </div>
</template>

<script setup>
import Header from './components/Header.vue'
</script>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  --primary: #b8383b;
  --primary-light: #d4545a;
  --bg: #faf6f2;
  --bg-card: #ffffff;
  --text: #2c2c2c;
  --text-light: #666;
  --border: #e8e0d8;
  --shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  --radius: 8px;
}

body {
  font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  min-height: 100vh;
}

a {
  color: var(--primary);
  text-decoration: none;
}

a:hover {
  color: var(--primary-light);
}

.container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px 16px;
  min-height: calc(100vh - 160px);
}

.footer {
  text-align: center;
  padding: 20px;
  color: var(--text-light);
  font-size: 13px;
  border-top: 1px solid var(--border);
}

.btn {
  display: inline-block;
  padding: 8px 20px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn:hover {
  background: var(--primary-light);
}

.btn-outline {
  background: transparent;
  color: var(--primary);
  border: 1px solid var(--primary);
}

.btn-outline:hover {
  background: var(--primary);
  color: #fff;
}

.card {
  background: var(--bg-card);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 20px;
  margin-bottom: 16px;
}

input,
select,
textarea {
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 14px;
  font-family: inherit;
  width: 100%;
  transition: border-color 0.2s;
}

input:focus,
select:focus,
textarea:focus {
  outline: none;
  border-color: var(--primary);
}

.tag {
  display: inline-block;
  padding: 2px 10px;
  background: #f0e6e6;
  color: var(--primary);
  border-radius: 12px;
  font-size: 12px;
  margin: 2px 4px 2px 0;
}

.loading {
  text-align: center;
  padding: 40px;
  color: var(--text-light);
}

.empty {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-light);
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3 {
  margin-top: 1em;
  margin-bottom: 0.5em;
}

.markdown-body p {
  margin-bottom: 0.8em;
}

.markdown-body ul,
.markdown-body ol {
  padding-left: 1.5em;
  margin-bottom: 0.8em;
}
</style>
