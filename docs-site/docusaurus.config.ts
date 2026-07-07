import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'dicomqc Docs',
  tagline: 'A policy-driven, standards-aware audit framework for validating DICOM de-identification and research-release readiness',
  url: 'https://cnag-biomedical-informatics.github.io',
  baseUrl: '/dicomqc/',
  organizationName: 'mrueda',
  projectName: 'dicomqc',
  onBrokenLinks: 'warn',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },
  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: 'docs',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],
  themes: [
    [
      '@easyops-cn/docusaurus-search-local',
      {
        hashed: true,
        language: ['en'],
        indexDocs: true,
        indexBlog: false,
        docsRouteBasePath: '/docs',
      },
    ],
  ],
  themeConfig: {
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'dicomqc',
      logo: {
        alt: 'dicomqc logo',
        src: 'img/dicomqc-logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          to: '/docs/usage/quickstart',
          label: 'Quick Start',
          position: 'left',
        },
        {
          href: 'https://github.com/mrueda/dicomqc',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'Overview',
              to: '/docs/overview',
            },
            {
              label: 'Quick Start',
              to: '/docs/usage/quickstart',
            },
            {
              label: 'CLI Reference',
              to: '/docs/reference/cli',
            },
            {
              label: 'Prior Work',
              to: '/docs/about/prior-work',
            },
          ],
        },
        {
          title: 'Project',
          items: [
            {
              label: 'Repository',
              href: 'https://github.com/mrueda/dicomqc',
            },
            {
              label: 'CNAG',
              href: 'https://www.cnag.eu',
            },
          ],
        },
      ],
      copyright: 'Copyright © 2026 Manuel Rueda, CNAG.',
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
