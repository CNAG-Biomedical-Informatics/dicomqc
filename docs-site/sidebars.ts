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
          id: 'usage/quickstart',
          label: 'Quickstart',
        },
        {
          type: 'doc',
          id: 'usage/reports',
          label: 'Reports',
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
          label: 'Extending DICOMQC',
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
