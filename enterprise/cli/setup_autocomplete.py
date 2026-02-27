#!/usr/bin/env python3
"""
DragonScope CLI Autocomplete Setup
===================================

Sets up shell autocompletion for the DragonScope CLI.

Supported shells:
    - Bash
    - Zsh
    - Fish

Usage:
    python setup_autocomplete.py [--shell {bash,zsh,fish}]
"""

import os
import sys
import click
from pathlib import Path


def setup_bash():
    """Setup Bash autocompletion."""
    click.echo("Setting up Bash autocompletion...")
    
    # Generate completion script
    completion_script = '''
# DragonScope CLI Bash Completion
_dragonscope_complete() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    # Main commands
    local commands="status logs deploy config db cache backup restore monitor test shell promote rollback"
    
    # Options for each command
    case "${COMP_WORDS[1]}" in
        status)
            opts="--watch --service --env --help"
            ;;
        logs)
            opts="--env --follow --tail --since --grep --level --help"
            ;;
        deploy)
            opts="--version --strategy --canary-percentage --wait --dry-run --skip-tests --help"
            ;;
        config)
            opts="get set list --env --help"
            ;;
        db)
            opts="migrate rollback status seed --env --version --steps --help"
            ;;
        cache)
            opts="--service --all --env --pattern --help"
            ;;
        backup)
            opts="--s3 --encrypt --retention --database --files --help"
            ;;
        restore)
            opts="--env --s3 --database --files --help"
            ;;
        monitor)
            opts="--env --service --help"
            ;;
        test)
            opts="--unit --integration --e2e --coverage --parallel --failed --watch --help"
            ;;
        shell)
            opts="--env --command --help"
            ;;
        *)
            opts=""
            ;;
    esac
    
    if [[ ${cur} == -* ]]; then
        COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
        return 0
    fi
    
    if [ $COMP_CWORD -eq 1 ]; then
        COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
        return 0
    fi
}

complete -F _dragonscope_complete ds
complete -F _dragonscope_complete dragonscope
'''
    
    # Determine completion directory
    completion_dir = Path.home() / ".bash_completion.d"
    if not completion_dir.exists():
        completion_dir.mkdir(parents=True, exist_ok=True)
    
    completion_file = completion_dir / "dragonscope"
    
    with open(completion_file, 'w') as f:
        f.write(completion_script)
    
    # Add to .bashrc if not already there
    bashrc = Path.home() / ".bashrc"
    source_line = f"source {completion_file}"
    
    if bashrc.exists():
        content = bashrc.read_text()
        if str(completion_file) not in content:
            with open(bashrc, 'a') as f:
                f.write(f"\n# DragonScope CLI completion\n{source_line}\n")
    
    click.echo(f"✓ Bash completion installed to: {completion_file}")
    click.echo("  Restart your shell or run: source ~/.bashrc")


def setup_zsh():
    """Setup Zsh autocompletion."""
    click.echo("Setting up Zsh autocompletion...")
    
    completion_script = '''#compdef ds dragonscope

# DragonScope CLI Zsh Completion

_dragonscope() {
    local curcontext="$curcontext" state line
    typeset -A opt_args

    local -a commands
    commands=(
        'status:Show service status'
        'logs:Stream service logs'
        'deploy:Deploy to environment'
        'config:Manage configuration'
        'db:Database operations'
        'cache:Cache management'
        'backup:Create backup'
        'restore:Restore from backup'
        'monitor:Open monitoring dashboard'
        'test:Run test suite'
        'shell:Open shell in container'
        'promote:Promote between environments'
        'rollback:Rollback deployment'
    )

    _arguments -C \\
        '(-h --help)'{-h,--help}'[Show help]' \\
        '(-v --verbose)'{-v,--verbose}'[Verbose output]' \\
        '1: :->command' \\
        '*:: :->args'

    case "$state" in
        command)
            _describe -t commands 'dragonscope command' commands
            ;;
        args)
            case "$line[1]" in
                status)
                    _arguments \\
                        '(-w --watch)'{-w,--watch}'[Watch mode]' \\
                        '(-s --service)'{-s,--service}'[Filter by service]:service:' \\
                        '(-e --env)'{-e,--env}'[Environment]:env:(development staging production)'
                    ;;
                logs)
                    _arguments \\
                        '(-e --env)'{-e,--env}'[Environment]:env:(development staging production)' \\
                        '(-f --follow)'{-f,--follow}'[Follow output]' \\
                        '(-t --tail)'{-t,--tail}'[Number of lines]:lines:' \\
                        '(-s --since)'{-s,--since}'[Since duration]:duration:' \\
                        '(-g --grep)'{-g,--grep}'[Filter pattern]:pattern:' \\
                        '(-l --level)'{-l,--level}'[Log level]:level:(DEBUG INFO WARN ERROR FATAL)'
                    ;;
                deploy)
                    _arguments \\
                        '(-v --version)'{-v,--version}'[Version to deploy]:version:' \\
                        '(-s --strategy)'{-s,--strategy}'[Deployment strategy]:strategy:(rolling blue-green canary)' \\
                        '--canary-percentage[Canary traffic percentage]:percentage:' \\
                        '(-w --wait)'{-w,--wait}'[Wait for completion]' \\
                        '--dry-run[Show without deploying]' \\
                        '--skip-tests[Skip pre-deployment tests]' \\
                        '1:environment:(development staging production)'
                    ;;
                db)
                    local -a db_commands
                    db_commands=(
                        'migrate:Run migrations'
                        'rollback:Rollback migrations'
                        'status:Show migration status'
                        'seed:Seed database'
                    )
                    _describe -t db_commands 'db command' db_commands
                    ;;
                *)
                    _files
                    ;;
            esac
            ;;
    esac
}

_dragonscope "$@"
'''
    
    # Zsh completion directories
    zsh_dirs = [
        Path.home() / ".zsh/completions",
        Path.home() / ".zsh-completions",
        Path("/usr/local/share/zsh/site-functions"),
    ]
    
    completion_file = None
    for d in zsh_dirs:
        if d.exists() or d.parent.exists():
            d.mkdir(parents=True, exist_ok=True)
            completion_file = d / "_dragonscope"
            break
    
    if completion_file is None:
        # Create in home directory
        completion_dir = Path.home() / ".zsh/completions"
        completion_dir.mkdir(parents=True, exist_ok=True)
        completion_file = completion_dir / "_dragonscope"
        
        # Add to fpath in .zshrc
        zshrc = Path.home() / ".zshrc"
        if zshrc.exists():
            content = zshrc.read_text()
            if str(completion_dir) not in content:
                with open(zshrc, 'a') as f:
                    f.write(f"\n# DragonScope CLI completion\nfpath+={completion_dir}\n")
    
    with open(completion_file, 'w') as f:
        f.write(completion_script)
    
    click.echo(f"✓ Zsh completion installed to: {completion_file}")
    click.echo("  Restart your shell or run: compinit")


def setup_fish():
    """Setup Fish autocompletion."""
    click.echo("Setting up Fish autocompletion...")
    
    completion_dir = Path.home() / ".config/fish/completions"
    completion_dir.mkdir(parents=True, exist_ok=True)
    
    completion_file = completion_dir / "ds.fish"
    
    completion_script = '''# DragonScope CLI Fish Completion

# Main commands
complete -c ds -f
complete -c dragonscope -f

# Global options
complete -c ds -s h -l help -d "Show help"
complete -c ds -s v -l verbose -d "Verbose output"
complete -c ds -l version -d "Show version"

# Commands
complete -c ds -n '__fish_use_subcommand' -a status -d "Show service status"
complete -c ds -n '__fish_use_subcommand' -a logs -d "Stream service logs"
complete -c ds -n '__fish_use_subcommand' -a deploy -d "Deploy to environment"
complete -c ds -n '__fish_use_subcommand' -a config -d "Manage configuration"
complete -c ds -n '__fish_use_subcommand' -a db -d "Database operations"
complete -c ds -n '__fish_use_subcommand' -a cache -d "Cache management"
complete -c ds -n '__fish_use_subcommand' -a backup -d "Create backup"
complete -c ds -n '__fish_use_subcommand' -a restore -d "Restore from backup"
complete -c ds -n '__fish_use_subcommand' -a monitor -d "Open monitoring dashboard"
complete -c ds -n '__fish_use_subcommand' -a test -d "Run test suite"
complete -c ds -n '__fish_use_subcommand' -a shell -d "Open shell in container"
complete -c ds -n '__fish_use_subcommand' -a promote -d "Promote between environments"
complete -c ds -n '__fish_use_subcommand' -a rollback -d "Rollback deployment"

# Command options
complete -c ds -n '__fish_seen_subcommand_from status' -s w -l watch -d "Watch mode"
complete -c ds -n '__fish_seen_subcommand_from status' -s s -l service -d "Filter by service"
complete -c ds -n '__fish_seen_subcommand_from status' -s e -l env -a "development staging production" -d "Environment"

complete -c ds -n '__fish_seen_subcommand_from logs' -s e -l env -a "development staging production" -d "Environment"
complete -c ds -n '__fish_seen_subcommand_from logs' -s f -l follow -d "Follow output"
complete -c ds -n '__fish_seen_subcommand_from logs' -s t -l tail -d "Number of lines"
complete -c ds -n '__fish_seen_subcommand_from logs' -s s -l since -d "Since duration"
complete -c ds -n '__fish_seen_subcommand_from logs' -s g -l grep -d "Filter pattern"
complete -c ds -n '__fish_seen_subcommand_from logs' -s l -l level -a "DEBUG INFO WARN ERROR FATAL" -d "Log level"

complete -c ds -n '__fish_seen_subcommand_from deploy' -s v -l version -d "Version to deploy"
complete -c ds -n '__fish_seen_subcommand_from deploy' -s s -l strategy -a "rolling blue-green canary" -d "Deployment strategy"
complete -c ds -n '__fish_seen_subcommand_from deploy' -l canary-percentage -d "Canary traffic percentage"
complete -c ds -n '__fish_seen_subcommand_from deploy' -s w -l wait -d "Wait for completion"
complete -c ds -n '__fish_seen_subcommand_from deploy' -l dry-run -d "Show without deploying"
complete -c ds -n '__fish_seen_subcommand_from deploy' -l skip-tests -d "Skip pre-deployment tests"

complete -c ds -n '__fish_seen_subcommand_from config' -a "get set list"

complete -c ds -n '__fish_seen_subcommand_from db' -a "migrate rollback status seed"

complete -c ds -n '__fish_seen_subcommand_from test' -s u -l unit -d "Run unit tests"
complete -c ds -n '__fish_seen_subcommand_from test' -s i -l integration -d "Run integration tests"
complete -c ds -n '__fish_seen_subcommand_from test' -l e2e -d "Run end-to-end tests"
complete -c ds -n '__fish_seen_subcommand_from test' -s c -l coverage -d "Generate coverage report"
complete -c ds -n '__fish_seen_subcommand_from test' -s p -l parallel -d "Run tests in parallel"
complete -c ds -n '__fish_seen_subcommand_from test' -s f -l failed -d "Run only failed tests"
complete -c ds -n '__fish_seen_subcommand_from test' -s w -l watch -d "Watch mode"
'''
    
    with open(completion_file, 'w') as f:
        f.write(completion_script)
    
    # Also create for 'dragonscope' command
    dragonscope_file = completion_dir / "dragonscope.fish"
    with open(dragonscope_file, 'w') as f:
        f.write(completion_script.replace('-c ds ', '-c dragonscope '))
    
    click.echo(f"✓ Fish completion installed to: {completion_file}")
    click.echo("  Completion will be available in new Fish sessions")


@click.command()
@click.option('--shell', type=click.Choice(['bash', 'zsh', 'fish', 'auto']), 
              default='auto', help='Shell to setup completion for')
def main(shell):
    """Setup shell autocompletion for DragonScope CLI."""
    
    if shell == 'auto':
        # Detect shell from environment
        shell_path = os.environ.get('SHELL', '')
        if 'bash' in shell_path:
            shell = 'bash'
        elif 'zsh' in shell_path:
            shell = 'zsh'
        elif 'fish' in shell_path:
            shell = 'fish'
        else:
            click.echo("Could not detect shell. Please specify with --shell")
            sys.exit(1)
        
        click.echo(f"Detected shell: {shell}")
    
    if shell == 'bash':
        setup_bash()
    elif shell == 'zsh':
        setup_zsh()
    elif shell == 'fish':
        setup_fish()
    
    click.echo()
    click.echo("Autocomplete setup complete! 🎉")
    click.echo("You may need to restart your shell for changes to take effect.")


if __name__ == '__main__':
    main()
