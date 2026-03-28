# Component Equivalence Matrix

Cross-library mapping of common UI components. Use when migrating between libraries, recommending component swaps, or generating code for a specific library.

**Sources:** [MUI](https://github.com/mui/material-ui) | [Ant Design](https://ant.design/components/overview) | [Chakra UI](https://www.chakra-ui.com/docs/components/concepts/overview) | [Radix UI](https://www.radix-ui.com/primitives/docs/components) | [shadcn/ui](https://ui.shadcn.com/docs/components)

---

### Component equivalence matrix (canonical component -> MUI -> Ant -> Chakra -> Radix / Headless -> shadcn / Tailwind)

| **Component**                   | **MUI (example import)** | **Ant Design (example import)** | **Chakra (example import)** | **Radix / Headless (example import)** | **shadcn / Tailwind (example import)** |
| ------------------------------- | -------------------------------------------------: | ---------------------------------------: | --------------------------------------------: | -----------------------------------------------------------: | ------------------------------------------------------: |
| **Button**                      | `import Button from '@mui/material/Button';` | `import { Button } from 'antd';` | `import { Button } from '@chakra-ui/react';` | `unstyled primitive + styled wrapper` | `export function Button(props){/* tailwind classes */}` |
| **Input / TextField**           | `import TextField from '@mui/material/TextField';` | `import { Input } from 'antd';` | `import { Input } from '@chakra-ui/react';` | `use Radix/textfield or headless input` | `input className="..."` |
| **Modal / Dialog**              | `import Dialog from '@mui/material/Dialog';` | `import { Modal } from 'antd';` | `import { Modal } from '@chakra-ui/react';` | `import * as Dialog from '@radix-ui/react-dialog';` | `Dialog (shadcn) + Headless primitives` |
| **Popover / Tooltip**           | `import Popover from '@mui/material/Popover';` | `import { Tooltip } from 'antd';` | `import { Tooltip } from '@chakra-ui/react';` | `import * as Popover from '@radix-ui/react-popover';` | `Popover built with radix + tailwind` |
| **Menu / Dropdown**             | `import Menu from '@mui/material/Menu';` | `import { Dropdown, Menu } from 'antd';` | `import { Menu } from '@chakra-ui/react';` | `import * as DropdownMenu from '@radix-ui/react-dropdown-menu';` | `Menu component (shadcn)` |
| **Select / Combobox**           | `import Select from '@mui/material/Select';` | `import { Select } from 'antd';` | `import { Select } from '@chakra-ui/react';` | `import * as Select from '@radix-ui/react-select';` | `Combobox (shadcn) using headless primitives` |
| **Table / DataGrid**            | `import Table from '@mui/material/Table';` | `import { Table } from 'antd';` | `import { Table } from '@chakra-ui/react';` | `headless table primitives or TanStack Table` | `Table components built with tailwind` |
| **Form / Validation**           | `useForm + MUI inputs` | `Form + Form.Item` | `FormControl + FormLabel` | `headless inputs + aria patterns` | `form components + react-hook-form patterns` |
| **Toast / Notification**        | `useSnackbar (MUI)` | `notification` | `useToast()` | `toast primitives or headless` | `sonner/toast + shadcn wrappers` |
| **Tabs / Accordion / Collapse** | `Tabs, Accordion` | `Tabs, Collapse` | `Tabs, Accordion` | `Tabs, Accordion primitives` | `Tailwind + radix variants` |
| **DatePicker / Calendar**       | `DatePicker (lab/x)` | `DatePicker` | `DatePicker (community)` | `headless date primitives` | `date-picker components (shadcn)` |

*(Each cell is a one-line canonical import or pattern; many libraries provide both styled and unstyled/base variants.)*

---

### Key implementation notes for your AI agents

- **Prefer primitive -> styled mapping:** when recommending swaps, map Radix/Headless primitives to the target styled component (e.g., Radix `Dialog` -> MUI `Dialog`) so the agent can generate both markup and style layers. Radix and [Headless UI](https://headlessui.com/) are the canonical "source of truth" for behavior.
- **Form equivalence:** treat Form as a pattern (inputs + validation hooks) rather than a single component; map to `react-hook-form` + library inputs.
- **Data grids:** map to specialized packages (MUI X DataGrid, Ant ProTable, TanStack Table) rather than generic Table for performance features.

---

### Risks, trade-offs, and recommendations

- **Bundle size:** swapping into full design systems (MUI/Ant) increases bundle size; prefer headless + Tailwind for minimal runtime. Measure before recommending.
- **Accessibility:** Radix/Headless UI and Chakra emphasize ARIA patterns -- use them as canonical behavior sources.
