from __future__ import print_function, absolute_import, division

import codecs
import os
import re
import sys
# add
import datetime

from jinja2 import FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment
from sphinx.jinja2glue import BuiltinTemplateLoader
from sphinx.util.osutil import ensuredir

#from . import import_by_name
# add
from . import import_by_name, get_doxygen_root
from ..xmlutils import format_xml_paragraph

# add
def is_type(node):
    def_node = get_doxygen_root().find('./compounddef[@id="%s"]' % node.get('refid'))
    return def_node.get('kind') == 'type'

def generate_autosummary_docs(sources, output_dir=None, suffix='.rst',
                              #base_path=None, builder=None, template_dir=None):
                              # add toctree argument
                              base_path=None, builder=None, template_dir=None, toctree=None,
                              build_mode=None):

    showed_sources = list(sorted(sources))
    if len(showed_sources) > 20:
        showed_sources = showed_sources[:10] + ['...'] + showed_sources[-10:]
    print('[autosummary] generating autosummary for: %s' %
          ', '.join(showed_sources))

    if output_dir:
        print('[autosummary] writing to %s' % output_dir)

    if base_path is not None:
        sources = [os.path.join(base_path, filename) for filename in sources]

    # create our own templating environment
    template_dirs = [os.path.join(os.path.dirname(__file__), 'templates')]

    if builder is not None:
        # allow the user to override the templates
        template_loader = BuiltinTemplateLoader()
        template_loader.init(builder, dirs=template_dirs)
    else:
        if template_dir:
            template_dirs.insert(0, template_dir)
        template_loader = FileSystemLoader(template_dirs)
    #template_env = SandboxedEnvironment(loader=template_loader)
    # modified
    template_env = SandboxedEnvironment(loader=template_loader,
                                        trim_blocks=True, lstrip_blocks=True)

    # read
    items = find_autosummary_in_files(sources)

    # keep track of new files
    new_files = []

    for name, path, template_name in sorted(set(items), key=str):
        # replace
        path = path or output_dir or os.path.abspath(toctree)
        # debug
        #import pdb; pdb.set_trace()

        # this is extra?
        #if path is None:
        #    # The corresponding autosummary:: directive did not have
        #    # a :toctree: option
        #    print("[debug] directive did not have a :toctree: option")
        #    continue

        #path = output_dir or os.path.abspath(path)
        if builder.app.verbosity > 0:
            print("[debug] checking path: %s" % (path))
        ensuredir(path)

        try:
            name, obj, parent, mod_name = import_by_name(name)
        except ImportError as e:
            print('WARNING [autosummary] failed to import %r: %s' % (name, e), file=sys.stderr)
            continue

        fn = os.path.join(path, name + suffix).replace('::', '.')

        # skip it if it exists
        if os.path.isfile(fn):
            continue

        # removed?
        #new_files.append(fn)

        if template_name is None:
            if obj.tag == 'compounddef' and obj.get('kind') == 'class':
                template_name = 'doxyclass.rst'
            elif obj.tag == 'compounddef' and obj.get('kind') in ['namespace', 'module']:
                template_name = 'doxynamespace.rst'
            elif obj.tag == 'compounddef' and obj.get('kind') == 'page':
                template_name = 'doxypage.rst'
            else:
                # change
                raise NotImplementedError('No template for %s (%s %s)' % (obj.items(), obj.tag, obj.get('kind')))

        if builder.app.verbosity > 0:
            print("[debug] template:%s kind: %s obj.items():%s" % (template_name, obj.get('kind'), obj.items()))
        with open(fn, 'w') as f:
            # debug
            #import pdb; pdb.set_trace()
            template = template_env.get_template(template_name)
            # The ns keys feed into the template
            ns = {}
            if obj.tag == 'compounddef' and obj.get('kind') == 'class':
                ns['methods'] = [e.text for e in obj.findall('.//sectiondef[@kind="public-func"]/memberdef[@kind="function"]/name')]
                ns['enums'] = [e.text for e in obj.findall('.//sectiondef[@kind="public-type"]/memberdef[@kind="enum"]/name')]
                ns['objtype'] = 'class'
            elif obj.tag == 'compounddef' and obj.get('kind') == 'namespace':
                ns['methods'] = [e.text for e in obj.findall('./sectiondef[@kind="func"]/memberdef[@kind="function"]/name')]
                ns['types'] = [e.text for e in obj.findall('./innerclass') if is_type(e)]
                ns['objtype'] = 'namespace'
            elif obj.tag == 'compounddef' and obj.get('kind') == 'page':
                if builder.app.verbosity > 0:
                    print("[debug] xml parsing for %s" % (obj.get('id')))
                ns['title'] = obj.find('title').text
                ns['underline'] = len(ns['title']) * '='
                #ns['text'] = format_xml_paragraph(obj.find('detaileddescription'),build_mode)
                ns = format_xml_paragraph(obj.find('detaileddescription'), build_mode, nsOrig=ns, verbosity=builder.app.verbosity)
                #if obj.get('id') == 'Specifics':
                #    import pdb; pdb.set_trace()
            else:
                raise NotImplementedError(obj)

            parts = name.split('::')
            mod_name, obj_name = '::'.join(parts[:-1]), parts[-1]

            ns['fullname'] = name
            ns['module'] = mod_name
            ns['objname'] = obj_name
            ns['name'] = parts[-1]
            if not('underline' in ns):
                ns['underline'] = len(name) * '='

            rendered = template.render(**ns)
            f.write(rendered)
            # debug: date/time caching hack
            # f.write('\n..\n   {}'.format(datetime.datetime.now()))

    # descend recursively to new files
    if new_files:
        generate_autosummary_docs(new_files, output_dir=output_dir,
                                  suffix=suffix, base_path=base_path, builder=builder,
                                  #template_dir=template_dir)
                                  # add toctree argument
                                  template_dir=template_dir, toctree=toctree)


def find_autosummary_in_files(filenames):
    """Find out what items are documented in source/*.rst.

    See `find_autosummary_in_lines`.
    """
    # todo: break when this doesn't exist
    # look for modules and standalone documentation pages, but *not* the index page
    # itself (which it links to from itself for some reason...)
    documented = []
    for filename in filenames:
        with codecs.open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.read().splitlines()
            documented.extend(find_autosummary_in_lines(lines, filename=filename))

    return documented


def find_autosummary_in_lines(lines, module=None, filename=None):
    """Find out what items appear in autosummary:: directives in the
    given lines.

    Returns a list of (name, toctree, template) where *name* is a name
    of an object and *toctree* the :toctree: path of the corresponding
    autosummary directive (relative to the root of the file name), and
    *template* the value of the :template: option. *toctree* and
    *template* ``None`` if the directive does not have the
    corresponding options set.
    """

    # add generate_arg_re
    autosummary_re      = re.compile(r'^(\s*)\.\.\s+autodoxysummary::\s*')
    toctree_arg_re      = re.compile(r'^\s+:toctree:\s*(.*?)\s*$')
    template_arg_re     = re.compile(r'^\s+:template:\s*(.*?)\s*$')
    kind_arg_re         = re.compile(r'^\s+:kind:\s*(.*?)\s*$')
    generate_arg_re     = re.compile(r'^\s+:generate:\s*$')
    autosummary_item_re = re.compile(r'^\s+(~?[_a-zA-Z][a-zA-Z0-9_.:]*)\s*.*?')

    documented = []

    toctree = None
    template = None
    in_autosummary = False
    generate = False
    base_indent = ""

    for line in lines:
        if in_autosummary:
            m = toctree_arg_re.match(line)
            if m:
                toctree = m.group(1)
                if filename:
                    toctree = os.path.join(os.path.dirname(filename),
                                           toctree)
                continue

            m = template_arg_re.match(line)
            if m:
                template = m.group(1).strip()
                continue

            # add

            m = generate_arg_re.match(line)
            if m:
                generate = True
                continue

            m = kind_arg_re.match(line)
            if m and generate:
                kind = m.group(1).strip()
                xpath = None
                if kind == 'mod':
                    xpath = './compound[@kind="namespace"]'
                elif kind == 'page':
                    xpath = './compound[@kind="page" and not(@refid="indexpage")]'

                if xpath is not None:
                    results = get_doxygen_root().xpath(xpath)
                    for result in results:
                        documented.append((result.find('name').text, toctree, template))

                continue

            # end add
            
            if line.strip().startswith(':'):
                continue  # skip options

            m = autosummary_item_re.match(line)
            if m:
                name = m.group(1).strip()
                if name.startswith('~'):
                    name = name[1:]
                documented.append((name, toctree, template))
                continue

            if not line.strip() or line.startswith(base_indent + " "):
                continue

            in_autosummary = False

        m = autosummary_re.match(line)
        if m:
            in_autosummary = True
            base_indent = m.group(1)
            toctree = None
            template = None
            # add
            generate = False
            continue

    return documented


def process_generate_options(app):
    genfiles = app.config.autosummary_generate
    # add
    toctree = app.config.autosummary_toctree
    # This is important to handle \htmlonly and \latexonly directives
    sphinx_build_mode = app.config.sphinx_build_mode

    if genfiles and not hasattr(genfiles, '__len__'):
        env = app.builder.env
        genfiles = [env.doc2path(x, base=None) for x in env.found_docs
                    if os.path.isfile(env.doc2path(x))]

    if not genfiles:
        return

    #debug: this is ok
    #import pdb; pdb.set_trace()
    ext = list(app.config.source_suffix)[0]
    genfiles = [genfile + (not genfile.endswith(ext) and ext or '')
                for genfile in genfiles]

    generate_autosummary_docs(genfiles, builder=app.builder,
    # add toctree argument
    #                         suffix=ext, base_path=app.srcdir)
                              suffix=ext, base_path=app.srcdir, toctree=toctree, build_mode=sphinx_build_mode)
