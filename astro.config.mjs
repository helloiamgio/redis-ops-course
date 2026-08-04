// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mermaid from 'astro-mermaid';

// https://astro.build/config
export default defineConfig({
  // Imposta `site` con l'URL definitivo per sitemap/canonical (facoltativo).
  // site: 'https://redis-ops-course.pages.dev',
  integrations: [
    // ⚠️ astro-mermaid DEVE precedere starlight: intercetta i blocchi ```mermaid
    // e li renderizza lato client (nessun headless browser al build → ok su CF Pages).
    mermaid({
      theme: 'dark',     // coerente col tema scuro fluo
      autoTheme: true,   // segue il toggle chiaro/scuro di Starlight
    }),
    starlight({
      title: 'Redis Operations',
      description:
        'Corso operativo enterprise su Redis: install, sicurezza, HA, cluster, monitoring e lab.',
      defaultLocale: 'it',
      locales: {
        root: { label: 'Italiano', lang: 'it' },
      },
      // Tema "rosa fluo, elegante"
      customCss: ['./src/styles/redis-theme.css'],
      // Tema dei blocchi di codice (Expressive Code)
      expressiveCode: {
        themes: ['github-dark-default', 'github-light'],
      },
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/helloiamgio/redis-ops-course',
        },
      ],
      sidebar: [
        { label: 'Introduzione', link: '/' },
        { label: '00 · Parti da qui', link: '/00-introduzione/' },
        { label: 'Cheatsheet comandi', link: '/cheatsheet/' },
        { label: 'Percorso · Running Redis at Scale', link: '/running-redis-at-scale/' },
        {
          label: 'Fondamenti',
          items: [
            { label: '01 · Architettura e fondamenti', link: '/01-architettura/' },
          ],
        },
        {
          label: 'Installazione e configurazione',
          items: [
            { label: '02 · Installazione standalone', link: '/02-installazione-standalone/' },
            { label: '03 · Configurazione e sicurezza', link: '/03-configurazione-sicurezza/' },
            { label: '04 · Persistenza', link: '/04-persistenza/' },
          ],
        },
        {
          label: 'Alta disponibilità e scaling',
          items: [
            { label: '05 · Replica e Sentinel', link: '/05-replica-sentinel/' },
            { label: '06 · Redis Cluster', link: '/06-cluster/' },
          ],
        },
        {
          label: 'Operatività',
          items: [
            { label: '07 · Monitoring e tuning', link: '/07-monitoring-tuning/' },
            { label: '13 · Connessioni e client tuning', link: '/13-connessioni-client-tuning/' },
            { label: '08 · Backup, upgrade, troubleshooting', link: '/08-backup-upgrade-troubleshooting/' },
          ],
        },
        {
          label: 'Pratica',
          items: [
            { label: '09 · Laboratori pratici', link: '/09-lab/' },
            { label: '10 · Casi d\u2019uso', link: '/10-casi-uso/' },
          ],
        },
        {
          label: 'Enterprise e cloud-native',
          items: [
            { label: '11 · Produzione enterprise', link: '/11-produzione-enterprise/' },
            { label: '12 · Kubernetes e OpenShift', link: '/12-kubernetes-openshift/' },
          ],
        },
        {
          label: 'Percorso hands-on · Scale',
          items: [
            { label: '00 · Setup dell\u2019ambiente', link: '/scale/00-setup/' },
            { label: '01 · Connessioni', link: '/scale/01-connessioni/' },
            { label: '02 · Persistenza e durabilit\u00e0', link: '/scale/02-persistenza/' },
            { label: '03 · Alta disponibilit\u00e0', link: '/scale/03-alta-disponibilita/' },
            { label: '04 · Scalabilit\u00e0', link: '/scale/04-scalabilita/' },
            { label: '05 · Osservabilit\u00e0', link: '/scale/05-osservabilita/' },
            { label: '06 · Capstone', link: '/scale/06-capstone/' },
          ],
        },
        { label: 'Repository e deploy', link: '/deploy/' },
      ],
    }),
  ],
});
