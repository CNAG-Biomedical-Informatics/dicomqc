import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    {
      type: 'doc',
      id: 'overview',
      label: 'Overview',
    },
    {
      type: 'category',
      label: 'Use',
      items: [
        {
          type: 'doc',
          id: 'usage/install',
          label: 'Install',
        },
        {
          type: 'doc',
          id: 'usage/quickstart',
          label: 'Quickstart',
        },
        {
          type: 'doc',
          id: 'usage/desktop',
          label: 'Desktop app',
        },
        {
          type: 'doc',
          id: 'usage/compare',
          label: 'Compare datasets',
        },
        {
          type: 'doc',
          id: 'usage/policies',
          label: 'Project policies',
        },
        {
          type: 'doc',
          id: 'usage/vendor-summary',
          label: 'Scanner inventory',
        },
        {
          type: 'doc',
          id: 'usage/uid-integrity',
          label: 'UID integrity',
        },
        {
          type: 'doc',
          id: 'usage/remediation',
          label: 'Remediation',
        },
        {
          type: 'doc',
          id: 'usage/ms-mri-workflow',
          label: 'MS MRI Workflow',
        },
      ],
    },
    {
      type: 'category',
      label: 'Technical Details',
      items: [
        {
          type: 'doc',
          id: 'technical-details/architecture',
          label: 'Architecture',
        },
        {
          type: 'doc',
          id: 'technical-details/extending-dicomqc',
          label: 'Planned Features',
        },
      ],
    },
    {
      type: 'category',
      label: 'Reference',
      items: [
        {
          type: 'doc',
          id: 'reference/cli',
          label: 'CLI',
        },
      ],
    },
    {
      type: 'category',
      label: 'About',
      items: [
        {
          type: 'doc',
          id: 'about/citation',
          label: 'Citation',
        },
        {
          type: 'doc',
          id: 'about/prior-work',
          label: 'Prior Work',
        },
        {
          type: 'doc',
          id: 'about/disclaimer',
          label: 'Disclaimer',
        },
      ],
    },
  ],
};

export default sidebars;
