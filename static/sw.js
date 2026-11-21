/**
 * Service Worker v2.4 - 完全绕过缓存的 pass-through.
 *
 * 之前 v2.1/v2.2 会缓存所有 GET 响应, 导致 src.zip / api.js 修复被旧版阻挡.
 * v2.3 加了 self-unregister, 但首次安装期间仍可能拦截.
 *
 * v2.4 改方案: 永不缓存, 永不读缓存, 立刻 unregister, 所有请求直达 Flask.
 * 这是 dev 阶段的临时方案, 生产部署 PWA 时再改回正常缓存策略.
 */

self.addEventListener('install', (event) => {
    console.log('[SW v2.4] installing (network-only mode)');
    event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
    console.log('[SW v2.4] activating, clearing all caches');
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => Promise.all(
                cacheNames.map((name) => caches.delete(name))
            ))
            .then(() => self.clients.claim())
            .then(() => {
                console.log('[SW v2.4] unregistering');
                return self.registration.unregister();
            })
    );
});

self.addEventListener('fetch', (event) => {
    // 永不读缓存, 直通网络
    event.respondWith(
        fetch(event.request).catch((err) => {
            console.warn('[SW v2.4] fetch failed:', err);
            return new Response('', { status: 504, statusText: 'Offline' });
        })
    );
});