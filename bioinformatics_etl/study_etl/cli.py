import click
from .etl import ETLProcessor
from .config import ConfigManager
from .validator import DataValidator
from .utils import setup_logging


@click.group()
@click.version_option()
@click.option('--verbose', '-v', is_flag=True)
@click.option('--quiet', '-q', is_flag=True)
@click.pass_context
def main(ctx, verbose, quiet):
    """Study ETL CLI Tool"""
    ctx.ensure_object(dict)
    setup_logging(verbose, quiet)


@main.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.argument('output_file', type=click.Path())
@click.option('--config', '-c', type=click.Path(exists=True))
@click.option('--format', 'output_format', type=click.Choice(['csv', 'json', 'excel']), default='csv')
@click.pass_context
def process(ctx, input_file, output_file, config, output_format):
    """Process data through ETL pipeline"""
    config_manager = ConfigManager(config)
    etl_config = config_manager.get_etl_config()
    processor = ETLProcessor(etl_config)
    
    click.echo(f"Processing {input_file} -> {output_file}")
    result = processor.process(input_file, output_file, output_format)
    
    if result:
        click.echo(f"Success: processed {result['rows_processed']} rows")
    else:
        click.echo("Processing failed")


@main.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--schema', '-s', type=click.Path(exists=True))
@click.option('--config', '-c', type=click.Path(exists=True))
@click.pass_context
def validate(ctx, input_file, schema, config):
    """Validate data against schema"""
    config_manager = ConfigManager(config)
    validation_config = config_manager.get_validation_config()
    
    if schema:
        validation_config['schema_file'] = schema
    
    validator = DataValidator(validation_config)
    is_valid, errors = validator.validate_file(input_file)
    
    if is_valid:
        click.echo("Data validation passed")
    else:
        click.echo(f"Validation failed with {len(errors)} errors")


@main.command()
@click.option('--output', '-o', type=click.Path(), default='config.yaml')
def init_config(output):
    """Generate sample configuration"""
    config_content = "etl:\n  input:\n    format: csv\n  validation:\n    enabled: true\n"
    with open(output, 'w') as f:
        f.write(config_content)
    click.echo(f"Configuration saved to {output}")


if __name__ == '__main__':
    main()