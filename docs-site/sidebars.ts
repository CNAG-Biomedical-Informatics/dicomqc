import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'overview',
    'usage/install',
    'usage/audit-modes',
    {type: 'category', label: 'Desktop App', items: [
      {type: 'doc', id: 'usage/desktop', label: 'Workspace and projects'},
      'usage/desktop-privacy', 'usage/desktop-comparison', 'usage/desktop-checks',
    ]},
    {type: 'category', label: 'CLI', items: [
      {type: 'doc', id: 'usage/quickstart', label: 'Privacy audit'},
      'usage/compare',
      {type: 'category', label: 'Optional checks and outputs', items: [
        'usage/policies', 'usage/uid-integrity', 'usage/vendor-summary',
      ]},
      {type: 'doc', id: 'reference/cli', label: 'Command reference'},
    ]},
    {type: 'category', label: 'Data preparation', items: [
      'usage/remediation', 'usage/ms-mri-workflow',
    ]},
    {type: 'category', label: 'Technical Details', items: [
      'technical-details/architecture',
    ]},
    {type: 'category', label: 'About', items: [
      'about/citation', 'about/prior-work', 'about/disclaimer',
    ]},
  ],
};

export default sidebars;
